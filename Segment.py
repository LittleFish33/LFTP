
# 数据包类
class Segment:
    def __init__(
            self,
            data = '',
            fileName = '',
            Seq = -1,
            rwnd = -1,
            Ack=-1,
            SYN = -1
    ):
        self.fileName = fileName
        self.Ack = Ack
        self.Seq = Seq
        self.rwnd = rwnd
        self.data = data
        self.syn = SYN