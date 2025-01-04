func twoSum(nums []int, target int) []int {
    m := make(map[int]int)
    var ans []int
    for idx, num := range nums {
        complement := target - num
        if c, ok := m[complement]; ok {
            ans = []int{c, idx}
            break
        }
        m[num] = idx
    }
    return ans     
}