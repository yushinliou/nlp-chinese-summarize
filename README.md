# Homework 3 ADL NTU：文本摘要任務
tmp 當中儲存的是模型、tokenizer，以及model config，而data當中則是訓練以及預測所需要的資料集。
模型原始訓練的環境是在colab上，python版本為3.7.15，如果使用3.8, 3.9可能會有無法import dataset套件的問題，故而在run.sh當中指定版本

# reproduce
```shell
# 下載model, tokenizer, data（public.jsonl, test_submission.jsonl, train.jsonl）
bash download.sh
# 需要傳入兩個參數，input以及output所在的位置
# 如果沒有特別指定則會存取./data/public.jsonl的檔案去預測，然後儲存在./pred/下面
bash ./run.sh path/to/pred_qa.csv
```

# train model
```shell
# 需要網路環境download model, tokenizer, 從hugging face 下載 pretrain model
# 如果要檢驗生成hightlight的rouge分數，需要另外執行cmd.ipnb生成的才會是正確的tw_rouge分數（需要網路環境以下載data.zip）
python ./sum.py
```

