# 206. Reverse Linked List
# Difficulty: Easy
# Runtime: 33 ms
# Memory: 18.4 MB

# Definition for singly-linked list.
# class ListNode:
#     def __init__(self, val=0, next=None):
#         self.val = val
#         self.next = next
class Solution:
    def reverseList(self, head: Optional[ListNode]) -> Optional[ListNode]:
        previous, current = None, head
        while current:
            nxt = current.next
            current.next = previous
            previous = current
            current = nxt
        return previous        
