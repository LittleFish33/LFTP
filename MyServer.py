import socket
import pickle
import _thread
import time

from Segment import *
from threading import Timer


from rdt import *



class MyServer():
    def __init__(
            self,
            serverIP = '127.0.0.1',
            bufferSize = 16,
            serverPort = 8888
    ):
        # 配置服务端的相关信息
        self.serverIP = serverIP
        self.bufferSize = bufferSize
        self.serverPort = serverPort

        # 启动数据连接，绑定端口
        self.serverSocket = self.initServer()
        self.serverSocket.bind((self.serverIP, self.serverPort))
        # 打印提示信息
        print('服务器已准备好接收连接...')
        # 每一个上传下载请求的相关信息保存在下面的字典中，上传/下载完毕之后从字典中移除
        self.recvDict = {}
        self.fileName = {}


    # 初始化socket
    def initServer(self):
        serverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        return serverSocket

    # 等待连接
    def waitForConnection(self):
        while True:
            # 接收到来自客户端的连接请求
            segment, clientAddress = self.serverSocket.recvfrom(1024)
            isLoadable = False
            try:
                # 使用pickle模块进行反序列化
                segment = pickle.loads(segment)
                isLoadable = True
            except:
                pass

            # 接收文件
            if isLoadable and isinstance(segment, Segment):
                self.receiveFile(segment,clientAddress)
            else:
                fileName = segment.decode('utf-8')
                # 来自客户端的下载请求
                if fileName[0:4] == 'lget':
                    fileName = fileName[5:]
                    print('接收到来自客户端 : ' + str(clientAddress) + ' 的 get 请求，文件名为：' + fileName)
                    # 新建线程发送数据
                    _thread.start_new_thread(self.sendFile, (fileName, clientAddress))

                # 来自客户端的上传请求
                elif fileName[0:5] == 'lsend':
                    fileName = fileName[6:]
                    print('接收到来自客户端 : ' + str(clientAddress) + ' 的 send 请求，文件名为：' + fileName)

                    # 往字典中添加对应的对象，这样就允许同时响应多个用户的请求
                    self.recvDict[clientAddress] = RdtReceiver()
                    self.fileName[clientAddress] = str(int(time.time()))


    # 服务端发送文件
    def sendFile(self, fileName, clientAddress):
        # 新建一个连接
        connectsocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 打开文件
        f = open(fileName, 'rb')
        rdtSender = RdtSender()
        flag = False
        seqNumber = -1

        # 发送数据包循环，发送完毕后退出
        while True:

            # flag用于判断慢启动是否已经结束
            if flag == False:

                # 发送速率实际上是由拥塞窗口，rwnd，和缓冲区的空闲空间中的最小值确定的
                rate = min(rdtSender.cwnd, rdtSender.rwnd,rdtSender.bufferSize - (rdtSender.lastByteSent - rdtSender.lastByteAcked))

                # 当接收窗口为0，发送零检验报文
                if rate == 0:
                    segmentSend = Segment()
                    self.sendPacket(rdtSender, connectsocket, clientAddress, segmentSend, 0)
                # 发送报文
                else:
                    for i in range(0,rate):
                        # 从文件中读取512个字节
                        data = f.read(512)
                        if len(data) == 0:
                            flag = True
                            break
                        seqNumber += 1
                        segmentSend = Segment(Seq=seqNumber, data=data)
                        rdtSender.store(i, segmentSend, False)
                        self.sendPacket(rdtSender, connectsocket, clientAddress, segmentSend, 0)

                        print("数据包 " + str(seqNumber) + " 已发送\n")
                        rdtSender.printBuffer()
            if flag == True and rdtSender.emptyBuffer():
                break


            while True:
                segment, clientAddress = connectsocket.recvfrom(1024)
                segment = pickle.loads(segment)
                if isinstance(segment,Segment):
                    # 更新接收窗口
                    if segment.Ack == -1:
                        rdtSender.rwnd = segment.rwnd
                        break

                    else:
                        # 接收到Ack包
                        rwnd = segment.rwnd
                        rdtSender.rwnd = rwnd
                        ack = segment.Ack
                        print("接收到来自数据包: " + str(ack) + " 的Ack回复")
                        rdtSender.updatecwnd()

                        # 更新缓冲区
                        for j in range(0, rdtSender.bufferSize):
                            if rdtSender.buffer[j] != None:
                                if rdtSender.buffer[j][0].Seq == int(ack):
                                    rdtSender.buffer[j][1] = True
                                    rdtSender.buffer[j][2] += 1 # 收到ACK的次数加1
                                    rdtSender.Timer[ack].cancel()
                                    rdtSender.Timer[ack].join()
                                    break

                        # 打印调试信息
                        rdtSender.printBuffer()

                        # 更新缓冲区的数据包是否确认
                        if j == 0:
                            for k in range(0, rdtSender.bufferSize):
                                if rdtSender.buffer[k] != None:
                                    if rdtSender.buffer[k][1] == False:
                                        break
                                else:
                                    break

                            # 更细rdtSender的相关属性
                            rdtSender.lastByteAcked = rdtSender.buffer[k-1][0].Seq
                            if k == rdtSender.bufferSize-1:
                                rdtSender.buffer = [None] * rdtSender.bufferSize
                            else:
                                for t in range(k,rdtSender.bufferSize):
                                    rdtSender.buffer[t-k] = rdtSender.buffer[t]
                                for t in range(rdtSender.bufferSize - k,rdtSender.bufferSize):
                                    rdtSender.buffer[t] = None
                            break
                        rdtSender.printBuffer()
            # 如果整个文件已经发送完且缓冲区为空
            if flag and rdtSender.emptyBuffer():
                break
        print("连接关闭")

        # 关闭文件
        f.close()

        # 向服务端发送结束连接的请求
        segment = Segment(Seq=-100)
        connectsocket.sendto(pickle.dumps(segment), clientAddress)

        # 关闭连接
        connectsocket.close()


    # 发送数据包
    def sendPacket(self, rdtSender, connectsocket, clientAddress, segment, count):
        # 发送窗口大小为0，发送一个空的数据包
        if segment.Seq == -1:
            connectsocket.sendto(pickle.dumps(segment), clientAddress)
        else:
            # 第一次发送，发送信息
            if count == 0:
                print("发送数据包 : " + str(segment.Seq) + " ...")
            else:
                # 打印重新发送的信息
                print("第 " + str(count) + " 次重发数据包 : " + str(segment.Seq) + " ...")

                # 超时，更新阈值和拥塞窗口
                rdtSender.ssthresh = rdtSender.cwnd / 2
                rdtSender.cwnd = 1

            # 更新rdtSender的相关参数
            if segment.Seq > rdtSender.lastByteSent:
                rdtSender.lastByteSent = segment.Seq

            # 发送数据包
            connectsocket.sendto(pickle.dumps(segment), clientAddress)

            # 更新缓冲区
            for index in range(0, rdtSender.bufferSize):
                if rdtSender.buffer[index] != None:
                    if rdtSender.buffer[index][0].Seq == segment.Seq:
                        break
            # 设置计时器
            rdtSender.Timer[segment.Seq] = Timer(5, self.sendPacket, (rdtSender, connectsocket, clientAddress, segment, count+1))
            # 开启计时器
            rdtSender.Timer[segment.Seq].start()


    # 接收文件
    def receiveFile(self, segment, clientAddress):

        # 从字典中提取对应客户端IP地址的rdtReceiver
        if self.recvDict.get(clientAddress) != None:
            rdtReceiver = self.recvDict[clientAddress]
            if self.fileName.get(clientAddress) == None:
                return

            # 打开文件
            f = open(self.fileName[clientAddress], 'ab')

            # 如果是segment
            if isinstance(segment, Segment):
                seqNumber = segment.Seq
                if seqNumber == -1:
                    # 返回一个空包，该包的内容为空闲窗口的大小
                    segmentRwnd = Segment(rwnd=rdtReceiver.rwnd)
                    self.serverSocket.sendto(pickle.dumps(segmentRwnd), clientAddress)

                else:
                    # 接收到数据包
                    print('接收到数据包 : ' + str(seqNumber) + ' : ' + str(segment.data))

                    # 判断接收的数据包的序列号
                    if seqNumber <= rdtReceiver.LastByteRead:
                        f.close()
                        segmentAck = Segment(data='', Seq=-1, Ack=seqNumber, rwnd=rdtReceiver.rwnd)
                        self.serverSocket.sendto(pickle.dumps(segmentAck), clientAddress)
                        return
                    if seqNumber > rdtReceiver.LastByteRcvd:
                        rdtReceiver.LastByteRcvd = seqNumber

                    # 更新缓冲区
                    for k in range(0, rdtReceiver.rcvBuffer):
                        if seqNumber == rdtReceiver.bufferBegin + k:
                            if rdtReceiver.buffer[k] == None:
                                rdtReceiver.buffer[k] = segment
                                break


                    # 更新拥塞窗口
                    rdtReceiver.updateRwnd()

                    # 计算左移的位数
                    for k in range(0, rdtReceiver.rcvBuffer):
                        if rdtReceiver.buffer[k] != None:
                            f.write(rdtReceiver.buffer[k].data)
                            rdtReceiver.LastByteRead = rdtReceiver.bufferBegin + k
                            break
                        else:
                            break

                    # 左移缓冲区
                    rdtReceiver.bufferLeftShift(k + 1)
                    rdtReceiver.bufferBegin = rdtReceiver.LastByteRead + 1
                    # 发送Ack报文
                    segmentAck = Segment(data='', Seq=-1, Ack=seqNumber, rwnd=rdtReceiver.rwnd)
                    self.serverSocket.sendto(pickle.dumps(segmentAck), clientAddress)

                # 关闭文件
                f.close()

                # 打印调试信息
                rdtReceiver.printBuffer()


if __name__ == '__main__':
    myServer = MyServer()
    myServer.waitForConnection()
