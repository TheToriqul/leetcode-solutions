/**
 * Note: The returned array must be malloced, assume caller calls free().
 */
int* twoSum(int* nums, int numsSize, int target, int* returnSize) {
    // Set return size to 2 as we need to return 2 indices
    *returnSize = 2;
    
    // Allocate memory for result array
    int* result = (int*)malloc(2 * sizeof(int));
    
    // Handle edge cases
    if (nums == NULL || numsSize < 2) {
        return result;
    }
    
    // Use nested loop to find the pair
    for (int i = 0; i < numsSize - 1; i++) {
        for (int j = i + 1; j < numsSize; j++) {
            // Check if current pair sums to target
            if (nums[i] + nums[j] == target) {
                result[0] = i;
                result[1] = j;
                return result;
            }
        }
    }
    
    return result;
}