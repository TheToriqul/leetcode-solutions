# 908. Middle of the Linked List
# Difficulty: Easy
# Runtime: 37 ms
# Memory: 17.3 MB

# Definition for singly-linked list.
# class ListNode:
#     def __init__(self, val=0, next=None):
#         self.val = val
#         self.next = next
class Solution:
    def middleNode(self, head: Optional[ListNode]) -> Optional[ListNode]:
        if head is None:
            return None

        slow = fast = head 
        while fast and fast.next:
            slow = slow.next
            fast = fast.next.next
        return slow       
