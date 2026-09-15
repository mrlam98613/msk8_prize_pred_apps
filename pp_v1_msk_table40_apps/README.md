# p_v2_table40_stand_mode 說明

## 程式重點

`p_v2_table40_stand_mode.py` 是 table40 查詢分析程式。

這支程式不是直接用 `1-40` 號碼範圍分析，而是將 `1-40` 拆成：

```text
idx_units = 1,2,3,4,5,6,7,8,9,0
idx_tens  = 0,1,2,3
```

每個球號都可以理解成：

```text
idx_tens.idx_units
```

這樣可以用較直覺的 table40 結構觀察開獎號：

```text
哪些 idx_units 經常出現
哪些 idx_units 不重複
哪些 idx_units 重複
同一期開獎號分布在哪些 idx_tens / idx_units
```

## table40 對應

`idx_units` 對應實際球號：

```text
idx_units 1 = 1, 11, 21, 31
idx_units 2 = 2, 12, 22, 32
idx_units 3 = 3, 13, 23, 33
idx_units 4 = 4, 14, 24, 34
idx_units 5 = 5, 15, 25, 35
idx_units 6 = 6, 16, 26, 36
idx_units 7 = 7, 17, 27, 37
idx_units 8 = 8, 18, 28, 38
idx_units 9 = 9, 19, 29, 39
idx_units 0 = 40, 10, 20, 30
```

`idx_tens` 是號碼所在的十位層：

```text
idx_tens 0 = 1-9 及 40
idx_tens 1 = 10-19
idx_tens 2 = 20-29
idx_tens 3 = 30-39
```

例子：

```text
7  = 0.7
18 = 1.8
24 = 2.4
33 = 3.3
40 = 0.0
10 = 1.0
20 = 2.0
30 = 3.0
```

特號用 `*` 顯示：

```text
11 = *1.1
38 = *3.8
```

## 核心參數

```python
SELECT_IDX_UNITS = (1,2,3,4,5,6,7,8,9,0)
```

這個參數選的是 `idx_units`，不是直接選 `1-40` 球號。

例如：

```python
SELECT_IDX_UNITS = (1,2,3,0)
```

代表查詢：

```text
idx_units 1 = 1,11,21,31
idx_units 2 = 2,12,22,32
idx_units 3 = 3,13,23,33
idx_units 0 = 40,10,20,30
```

輸入順序不影響查詢結果；重複輸入也不會令球數重複計算。

## 顯示模式

```python
IDX_DISPLAY_MODE = "idx_tens_units"
```

可選：

```text
idx_tens_units = 顯示完整 idx_tens.idx_units
idx_units      = 只顯示 idx_units
idx_units_dot  = 用 .N 顯示 idx_units
```

### idx_tens_units

完整顯示 table40 code：

```text
近  1期：2026-09-12，[0.9,1.8,2.4,3.3,0.0,_,*1.1] /> 5.5 球
```

這個模式使用一般球數：

```text
正號命中數 + 特號 0.5
```

### idx_units

只顯示 idx_units，並統計不重複的 idx_units：

```text
近  4期：2026-09-05，[9,8,6,0,3,_,*8] idx_units 不重復 [0,3,6,9] /> 4 球
```

例子中 `8` 出現兩次，所以不列入不重複統計。

### idx_units_dot

用點號顯示 idx_units，並統計重複球數：

```text
近 16期：2026-08-04，[.4,.1,.3,.6,.1,.3,*.8] idx_units 重復 [.1]=1,[.3]=1 /> 2 球
```

重複規則：

```text
同一 idx_units 出現 N 次，重複球數 = N - 1
```

所以 `.1` 出現 2 次，重複 1 球；`.3` 出現 2 次，重複 1 球。

## 球數統計自動配對

程式不再使用獨立的手動統計參數。

`IDX_DISPLAY_MODE` 會自動決定球數統計方式：

```text
idx_tens_units -> 合條件球數
idx_units      -> idx_units 不重複球數
idx_units_dot  -> idx_units 重複球數
```

## 合條件設定

```python
COMBINATION_TAKE_COUNT = 5
BIRTHDAY_NUM_MATCH_MODE = ">="
```

意思是：

```text
每期正號 N1..N6 中，命中所選 idx_units 至少 5 球，才會顯示。
```

注意：合條件判斷只看正號 N1..N6。特號只用於顯示和統計，不用於判斷該期是否合條件。

## 補位顯示

```python
DISPLAY_PAD_EMPTY = True
```

每期固定顯示 7 格：

```text
N1..N6 + N7 特號
```

沒有命中所選 `idx_units` 的位置，用 `_` 補位。

## Backtest / Predict

Backtest：

```python
MODE = "backtest"
```

窗口期不包括核對期，用核對期作下期驗證。

Predict：

```python
MODE = "predict"
```

窗口期包括最後一期已開獎資料，用作下期分析。

## 讀法總結

這支程式的核心不是問「哪些 1-40 號碼命中」，而是問：

```text
開獎號拆成 idx_tens / idx_units 後，
在 table40 結構中呈現什麼分布？
```

`idx_units` 負責查詢主軸，`idx_tens` 負責定位層次。兩者合起來，可以把 `1-40` 號碼轉成更直觀的 table40 觀察方式。
