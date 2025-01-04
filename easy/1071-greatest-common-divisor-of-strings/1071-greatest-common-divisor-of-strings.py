class Solution(object):
    def gcdOfStrings(self, str1, str2):
        """
        :type str1: str
        :type str2: str
        :rtype: str
        """

        len1 , len2 = len(str1) , len(str2)

        def isDivisor(p):
            if len1 % p or len2 % p:
                return False
            factor1 , factor2 = len1 / p , len2 / p
            return str1[:p] * factor1 == str1 and str1[:p] * factor2 == str2

        for i in range(min(len1,len2) , 0 , -1):
            if isDivisor(i):
                return str1[:i]
        return ""
        