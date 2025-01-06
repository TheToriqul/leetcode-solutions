class Solution {
public:
    vector<int> twoSum(vector<int>& nums, int target) {
        // Hash map to store number and its index
        unordered_map<int, int> numMap;
        
        // Iterate through the array
        for (int i = 0; i < nums.size(); i++) {
            // Calculate the complement needed
            int complement = target - nums[i];
            
            // Check if complement exists in hash map
            if (numMap.find(complement) != numMap.end()) {
                // Return current index and complement's index
                return {numMap[complement], i};
            }
            
            // If complement not found, add current number and index to hash map
            numMap[nums[i]] = i;
        }
        
        // No solution found (though problem guarantees a solution exists)
        return {};
    }
};