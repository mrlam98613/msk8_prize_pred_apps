'''
六合彩1..49球, 顏色分組
Red color ball
Blue color ball
Green color ball
https://www.cnblogs.com/yoyoketang/p/14604785.html
MSK lotto Draw number > 找出連續數字
'''
# from collections import Counter
# from numpy import empty



''' 傳入 list_num = [1,2,3,4,5,6,7] 分析成 RBG 顏色分組 回傳字典輸出'''
def res_List_To_rbg_Dict_func(inp_list1):
    '''
    input list_num = [1,2,3,4,5,6,7]
    convert to R,B,G Dict color group  = [1,2,7] [3,4] [5,6]
    '''
    p_list = list(inp_list1)
    rbg_dict_group = {0: [], 1: [], 2: []}
    

    for i in range(len(p_list)):
        s1 = p_list[i]
        if s1 > 0:
            x1 = res_call_RBG_123_func(s1)
            if x1 == 1:
                rbg_dict_group.setdefault(0, []).append(s1)
                
            if x1 == 2:
                rbg_dict_group.setdefault(1, []).append(s1)
                
            if x1 == 3:
                rbg_dict_group.setdefault(2, []).append(s1)
    return rbg_dict_group

''' 傳入 num = 1 分析成 RBG 顏色分組 回傳 1,2,3 輸出'''
def res_call_RBG_123_func(inp_num):  # <--str
    '''
    1 =  1.010, 2,=2.020, 3= 3.=0.30,
    11 = 3.110
    '''
    x = inp_num
    # 傳入字典, 可分成文字或, 數字
    # dict_double = {0: '1.0', 1: '2.0', 2: '3.0'}
    j_num = x - 1
    aa = (j_num // 10) + j_num
    bb = aa % 6
    res_RBG_num123 = (bb // 2) + 1
    # output_color = (j_num + j_num // 10) % 6 // 2 {寫成一行}
    # print(f'{res_RBG123}')
    return res_RBG_num123



# ''' 傳入 list_num = [1..49] 六合彩號碼，分析成 R,B,G ,1,2,3 類型 '''
# def res_msk_ToRBG_list_func(inp_list1):
#     '''
#     input list_num = [1,2,3,4,5,6,7]
#     identify to R,B,G = 1,2,3
#     '''
#     p_list = inp_list1
#     rbg_dict_group = {0: [], 1: [], 2: []}
#     rbg_123_list = {0: []}

#     for i in range(len(p_list)):
#         s1 = p_list[i]
#         if s1 > 0:
#             x1 = res_call_RBG_123_func(s1)
#             if x1 == 1:
#                 rbg_dict_group.setdefault(0, []).append(s1)
#                 rbg_123_list.setdefault(0, []).append(x1)
#             if x1 == 2:
#                 rbg_dict_group.setdefault(1, []).append(s1)
#                 rbg_123_list.setdefault(0, []).append(x1)
#             if x1 == 3:
#                 rbg_dict_group.setdefault(2, []).append(s1)
#                 rbg_123_list.setdefault(0, []).append(x1)

#     return rbg_dict_group, rbg_123_list


# ''' 傳入 list_num = [1,2,3,4,5,6,7] 分析成 RBG 顏色分組 回傳 [list] 輸出'''
# def res_list_to_RBG123_list_func(inp_list):
#     rbg_list = []
#     ''' 
#     傳入list 再分析成RBG 123
#     [3, 3, 1, 3, 1, 2, 2, 3, 3, 3]
#     '''
#     for i in range(len(inp_list)):
#         n1 = inp_list[i]
#         ''' call num to RBG123'''
#         rbg_num = res_call_RBG_123_func(n1)
#         rbg_list.append(rbg_num)

#     return rbg_list

