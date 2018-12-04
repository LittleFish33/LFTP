# -*-coding:utf-8-*-


class RdtReceiver:
    def __init__(self):
        self.rcvBuffer = 16  # 接收缓存的大小
        self.rwnd = self.rcvBuffer  # 接收窗口，一开始等于缓冲区的大小
        self.buffer = [None] * self.rcvBuffer  # 初始化接收缓冲区
        self.LastByteRead = -1 # 最后一个从缓存区读出到文件的字节编号
        self.LastByteRcvd = -1 # 最后一个接收到的字节的编号
        self.bufferBegin = 0 # 缓冲区开始位置的字节编号

    # 更新接收窗口
    def updateRwnd(self):
        self.rwnd = self.bufferBegin + self.rcvBuffer - self.LastByteRcvd

    # 更新缓冲区
    def bufferLeftShift(self, num):
        for i in range(0,self.rcvBuffer - num):
            self.buffer[i] = self.buffer[i+num]
        for i in range(self.rcvBuffer - num,self.rcvBuffer):
            self.buffer[i] = None

    # 打印一些调试信息
    def printBuffer(self):
        outStr = '接收方缓冲区：('
        for i in range(len(self.buffer)):
            if self.buffer[i] == None:
                outStr += 'None, '
            else:
                outStr += (str(self.buffer[i].Seq) + ', ')
        outStr += ')'
        outStr += ('  LastByteRead : ' + str(self.LastByteRead))
        outStr += (';  LastByteRcvd : ' + str(self.LastByteRcvd))
        outStr += (';  bufferBegin : ' + str(self.bufferBegin))
        print(outStr)


class RdtSender:
    def __init__(self):
        self.cwnd = 1  # 拥塞窗口，一开始等于1
        self.ssthresh = 5 # 阈值
        self.flag = False # 判断慢启动是否已经结束
        self.bufferSize = 16
        self.buffer = [None] * 16 # 初始化缓冲区，该缓冲区的目的仅仅是为了保存已发送但未被确认的分组
        self.rwnd = 16 # 接收方接收窗口的大小
        self.lastByteSent = -1 # 最后一个发送的字节的编号
        self.lastByteAcked = -1 # 最后一个确认的字节的编号
        self.Timer = {} # 缓冲区里的数据包的计时器，超时情况下再发送

    # 将已接收但未确认的数据包保存在缓冲区
    def store(self, index, segment, flag):
        bufferBegin = self.lastByteAcked + 1
        if segment.Seq - bufferBegin >= 0 and segment.Seq - bufferBegin < self.bufferSize:
            self.buffer[segment.Seq - bufferBegin] = [segment, flag, 0]

    # 判断缓冲区是否为空
    def emptyBuffer(self):
        for i in range(0,self.bufferSize):
            if self.buffer[i] != None:
                return False
        return True

    # 更新缓冲区
    def bufferLeftShift(self, num):
        for i in range(0,self.bufferSize - num):
            self.buffer[i] = self.buffer[i+num]
        for i in range(self.bufferSize - num,self.bufferSize):
            self.buffer[i] = None

    # 更新拥塞窗口
    def updatecwnd(self):
        # 慢启动
        if self.flag:
            if self.cwnd * 2 < self.ssthresh:
                self.cwnd *= 2
            else:
                self.cwnd += 1
                self.flag = False
        else:
            self.cwnd += 1

    # 打印一些调试信息
    def printBuffer(self):
        outStr = '发送方缓冲区：( '
        for i in range(len(self.buffer)):
            if self.buffer[i] == None:
                outStr += ('None, ')
            else:
                outStr += (str(self.buffer[i][0].Seq) + '[')
                if self.buffer[i][0].Ack == True:
                    outStr += ('True], ')
                else:
                    outStr += ('False], ')
        outStr += ') '
        outStr += (' lastByteSent : ' + str(self.lastByteSent))
        outStr += ';  lastByteAcked : ' + str(self.lastByteAcked)
        print(outStr)




