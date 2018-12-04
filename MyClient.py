import socket
import time

from rdt import *
from Segment import *
import pickle
from threading import Timer

from sys import argv


class MyClient():
    def __init__(
            self,
    ):
        self.clientSocket = self.initClient()

    # 初始化socket
    def initClient(self):
        clientSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return clientSocket

    # lget请求
    def lget(self, serverIP, serverPort, filename):
        # 建立连接请求
        self.clientSocket.sendto(filename, (serverIP, serverPort))
        rdtReceiver = RdtReceiver()
        while True:
            f = open(filename, 'ab')
            # 等待接收
            segment, serverAddress = self.clientSocket.recvfrom(1024)
            if serverAddress[0] == serverIP.decode('utf-8'):
                segment = pickle.loads(segment)
                if isinstance(segment, Segment):
                    seqNumber = segment.Seq
                    if seqNumber == -100:
                        f.close()
                        break
                    if seqNumber == -1:
                        segmentRwnd = Segment(rwnd=rdtReceiver.rwnd)
                        self.clientSocket.sendto(pickle.dumps(segmentRwnd), serverAddress)
                    else:
                        print('接收到数据包 : ' + str(seqNumber))
                        # 判断数据包的序列号
                        if seqNumber <= rdtReceiver.LastByteRead:
                            f.close()
                            segmentAck = Segment(data='', Seq=-1, Ack=seqNumber, rwnd=rdtReceiver.rwnd)
                            self.clientSocket.sendto(pickle.dumps(segmentAck), serverAddress)
                            continue
                        if seqNumber > rdtReceiver.LastByteRcvd:
                            rdtReceiver.LastByteRcvd = seqNumber
                        # 更新缓冲区
                        for k in range(0,rdtReceiver.rcvBuffer):
                            if seqNumber == rdtReceiver.bufferBegin + k:
                                if rdtReceiver.buffer[k] == None:
                                    rdtReceiver.buffer[k] = segment
                                    break
                        # 更新接收窗口
                        rdtReceiver.updateRwnd()
                        for k in range(0,rdtReceiver.rcvBuffer):
                            if rdtReceiver.buffer[k] != None:
                                f.write(rdtReceiver.buffer[k].data)
                                rdtReceiver.LastByteRead = rdtReceiver.bufferBegin + k
                                break
                            else:
                                break
                        rdtReceiver.bufferLeftShift(k+1)
                        # 发送Ack确认报文
                        rdtReceiver.bufferBegin = rdtReceiver.LastByteRead + 1
                        segmentAck = Segment(data='',Seq=-1,Ack=seqNumber,rwnd=rdtReceiver.rwnd)
                        self.clientSocket.sendto(pickle.dumps(segmentAck), serverAddress)
                        # 打印调试信息
                        rdtReceiver.printBuffer()
                    f.close()

    # lsend请求
    def lsend(self, serverIP, serverPort, fileName):
        # 请求建立连接
        self.clientSocket.sendto(fileName, (serverIP, serverPort))
        time.sleep(1)
        # 打开文件
        fileName = fileName[6:]
        f = open(fileName, 'rb')
        rdtSender = RdtSender()
        flag = False

        # 服务端地址
        serverAddress = (serverIP,serverPort)
        seqNumber = -1
        while True:
            if flag == False:

                # 根据接收窗口，拥塞窗口，缓冲区的空闲位置的最小值来更新发送速率
                rate = min(rdtSender.cwnd, rdtSender.rwnd,
                           rdtSender.bufferSize - (rdtSender.lastByteSent - rdtSender.lastByteAcked))
                # 当接收窗口为0，发送零检验报文
                if rate == 0:
                    segmentSend = Segment()
                    self.sendPacket(rdtSender, serverAddress, segmentSend, 0)
                # 发送报文
                else:
                    for i in range(0, rate):
                        # 从文件中读取512个字节
                        data = f.read(512)
                        if len(data) == 0:
                            flag = True
                            break
                        seqNumber += 1
                        segmentSend = Segment(Seq=seqNumber, data=data)
                        rdtSender.store(i, segmentSend, False)
                        self.sendPacket(rdtSender, serverAddress, segmentSend, 0)
                        print("数据包 " + str(seqNumber) + " 已发送\n")
                        rdtSender.printBuffer()
            if flag == True and rdtSender.emptyBuffer():
                break
            while True:
                segment, serverAddress = self.clientSocket.recvfrom(1024)
                segment = pickle.loads(segment)
                if isinstance(segment, Segment):
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
                                    # 收到ACK的次数加1
                                    rdtSender.buffer[j][2] += 1

                                    # 取消计时器
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
                            rdtSender.lastByteAcked = rdtSender.buffer[k - 1][0].Seq
                            if k == rdtSender.bufferSize - 1:
                                rdtSender.buffer = [None] * rdtSender.bufferSize
                            else:
                                for t in range(k, rdtSender.bufferSize):
                                    rdtSender.buffer[t - k] = rdtSender.buffer[t]
                                for t in range(rdtSender.bufferSize - k, rdtSender.bufferSize):
                                    rdtSender.buffer[t] = None
                            break
                        rdtSender.printBuffer()
            # 如果整个文件已经发送完且缓冲区为空
            if flag and rdtSender.emptyBuffer():
                break
        print("连接关闭")

        # 关闭文件
        f.close()

        # 关闭缓冲区
        self.clientSocket.close()



    # 发送数据包，count记录发送的次数
    def sendPacket(self, rdtSender, serverAddress, segment, count):
        # 发送窗口大小为0，发送一个空的数据包
        if segment.Seq == -1:
            self.clientSocket.sendto(pickle.dumps(segment), serverAddress)
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
            self.clientSocket.sendto(pickle.dumps(segment), serverAddress)

            # 更新缓冲区
            for index in range(0, rdtSender.bufferSize):
                if rdtSender.buffer[index] != None:
                    if rdtSender.buffer[index][0].Seq == segment.Seq:
                        break

            # 设置计时器
            rdtSender.Timer[segment.Seq] = Timer(5, self.sendPacket, (rdtSender, serverAddress, segment, count+1))
            # 开启定时器
            rdtSender.Timer[segment.Seq].start()


if __name__ == '__main__':
    myClient = MyClient()
    # 首先判断argv的长度是不是4
    if len(argv) == 4:
        # 获得IP,端口
        serverAddress = argv[2]
        serverIP, serverPort, flag = '', '', False
        for i in range(len(serverAddress)):
            if serverAddress[i] == ':':
                flag = True
                continue
            else:
                if flag:
                    serverPort += serverAddress[i]
                else:
                    serverIP += serverAddress[i]

        # 获取文件名
        fileName = argv[3]
        print(serverIP + ' ' + serverPort + ' ' + fileName)
        # 上传请求
        if argv[1] == 'lsend':
            fileName = 'lsend-' + fileName
            myClient.lsend(serverIP.encode('utf-8'), int(serverPort), fileName.encode('utf-8'))
        # 下载请求
        elif argv[1] == 'lget':
            fileName = 'lget-' + fileName
            myClient.lget(serverIP.encode('utf-8'), int(serverPort), fileName.encode('utf-8'))
    # 异常输入
    else:
        print('Please check your input')
