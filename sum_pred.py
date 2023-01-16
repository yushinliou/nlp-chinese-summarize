# -*- coding: utf-8 -*-
"""sum_pred.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1qtuWZWMtXu5qBghOBMBA0cBKYqZcXFqS

# import
"""

import os
# os.chdir('/content/drive/MyDrive/adl3/summarization')
os.system('pip install -r requirements_pred.txt')
os.system('pip install transformers')

from datasets import Dataset
import argparse
import json
import logging
import math
import os
import random
from pathlib import Path
import datasets
import nltk
import numpy as np
import torch
from datasets import load_dataset
from torch.utils.data import DataLoader
from tqdm.auto import tqdm
import transformers
from accelerate import Accelerator
from accelerate.logging import get_logger
from accelerate.utils import set_seed
from filelock import FileLock
from huggingface_hub import Repository
from transformers import (
    CONFIG_MAPPING,
    MODEL_MAPPING,
    AutoConfig,
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    SchedulerType,
    get_scheduler,
)
from transformers.utils import check_min_version, get_full_repo_name, is_offline_mode, send_example_telemetry
from transformers.utils.versions import require_version
import pandas as pd

logger = get_logger(__name__)
require_version("datasets>=1.8.0", "To fix: pip install -r examples/pytorch/summarization/requirements.txt")

# You should update this to your particular problem to have better documentation of `model_type`
MODEL_CONFIG_CLASSES = list(MODEL_MAPPING.keys())
MODEL_TYPES = tuple(conf.model_type for conf in MODEL_CONFIG_CLASSES)

try:
    nltk.data.find("tokenizers/punkt")
except (LookupError, OSError):
    if is_offline_mode():
        raise LookupError(
            "Offline mode: run this script without TRANSFORMERS_OFFLINE first to download nltk data files"
        )
    with FileLock(".lock") as lock:
        nltk.download("punkt", quiet=True)

summarization_name_mapping = {
    "amazon_reviews_multi": ("review_body", "review_title"),
    "big_patent": ("description", "abstract"),
    "cnn_dailymail": ("article", "highlights"),
    "orange_sum": ("text", "summary"),
    "pn_summary": ("article", "summary"),
    "psc": ("extract_text", "summary_text"),
    "samsum": ("dialogue", "summary"),
    "thaisum": ("body", "summary"),
    "xglue": ("news_body", "news_title"),
    "xsum": ("document", "summary"),
    "wiki_summary": ("article", "highlights"),
}

"""# args"""

def parse_args():
    parser = argparse.ArgumentParser(description="Finetune a transformers model on a summarization task")
    # ------------------------>
    parser.add_argument("--plan", type=str, default='ori',)
    parser.add_argument("--num_beams", type=int, default=None,)
    parser.add_argument("--do_sample", type=bool, default=None,)
    parser.add_argument("--top_k", type=int, default=None,)
    parser.add_argument("--top_p", type=float, default=None,)
    parser.add_argument("--temperature", type=float, default=None,)
    parser.add_argument('--no_repeat_ngram_size', type=int, default=None,)
    parser.add_argument(
        "--dataset_name",
        type=str,
        default='cnn_dailymail',
        help="The name of the dataset to use (via the datasets library).",
    )
    parser.add_argument(
        "--dataset_config_name",
        type=str,
        default=None,
        help="The configuration name of the dataset to use (via the datasets library).",
    )
    parser.add_argument(
        "--train_file", type=str, default=None, help="A csv or a json file containing the training data."
    )
    parser.add_argument(
        "--validation_file", type=str, default=None, help="A csv or a json file containing the validation data."
    )
    parser.add_argument(
        "--test_file", type=str, default='./data/public.jsonl', help="A csv or a json file containing the test data."
    )
    parser.add_argument(
        "--ignore_pad_token_for_loss",
        type=bool,
        default=True,
        help="Whether to ignore the tokens corresponding to padded labels in the loss computation or not.",
    )
    parser.add_argument(
        "--max_source_length",
        type=int,
        default=256,
        help=(
            "The maximum total input sequence length after "
            "tokenization.Sequences longer than this will be truncated, sequences shorter will be padded."
        ),
    )
    parser.add_argument(
        "--source_prefix",
        type=str,
        default='summarize: ',
        help="A prefix to add before every source text (useful for T5 models).",
    )
    parser.add_argument(
        "--preprocessing_num_workers",
        type=int,
        default=None,
        help="The number of processes to use for the preprocessing.",
    )
    parser.add_argument(
        "--overwrite_cache", action="store_true", help="Overwrite the cached training and evaluation sets"
    )
    parser.add_argument(
        "--max_target_length",
        type=int,
        default=64,
        help=(
            "The maximum total sequence length for target text after "
            "tokenization. Sequences longer than this will be truncated, sequences shorter will be padded."
            "during ``evaluate`` and ``predict``."
        ),
    )
    parser.add_argument(
        "--val_max_target_length",
        type=int,
        default=64,
        help=(
            "The maximum total sequence length for validation "
            "target text after tokenization.Sequences longer than this will be truncated, sequences shorter will be "
            "padded. Will default to `max_target_length`.This argument is also used to override the ``max_length`` "
            "param of ``model.generate``, which is used during ``evaluate`` and ``predict``."
        ),
    )
    parser.add_argument(
        "--max_length",
        type=int,
        default=256,
        help=(
            "The maximum total input sequence length after tokenization. Sequences longer than this will be truncated,"
            " sequences shorter will be padded if `--pad_to_max_lengh` is passed."
        ),
    )
    parser.add_argument(
        "--pad_to_max_length",
        action="store_true",
        help="If passed, pad all samples to `max_length`. Otherwise, dynamic padding is used.",
    )
    parser.add_argument(
        "--model_name_or_path",
        type=str,
        default='./tmp/',
        help="Path to pretrained model or model identifier from huggingface.co/models.",
        required=False,
    )
    parser.add_argument(
        "--config_name",
        type=str,
        default=None,
        help="Pretrained config name or path if not the same as model_name",
    )
    parser.add_argument(
        "--tokenizer_name",
        type=str,
        default=None,
        help="Pretrained tokenizer name or path if not the same as model_name",
    )
    parser.add_argument(
        "--text_column",
        type=str,
        default=None,
        help="The name of the column in the datasets containing the full texts (for summarization).",
    )
    parser.add_argument(
        "--summary_column",
        type=str,
        default=None,
        help="The name of the column in the datasets containing the summaries (for summarization).",
    )
    parser.add_argument(
        "--use_slow_tokenizer",
        action="store_true",
        help="If passed, will use a slow tokenizer (not backed by the 🤗 Tokenizers library).",
    )
    parser.add_argument(
        "--per_device_train_batch_size",
        type=int,
        default=4,
        help="Batch size (per device) for the training dataloader.",
    )
    parser.add_argument(
        "--per_device_eval_batch_size",
        type=int,
        default=32,
        help="Batch size (per device) for the evaluation dataloader.",
    )
    parser.add_argument(
        "--learning_rate",
        type=float,
        default=1e-04,
        help="Initial learning rate (after the potential warmup period) to use.",
    )
    parser.add_argument("--weight_decay", type=float, default=0.0, help="Weight decay to use.")
    parser.add_argument("--num_train_epochs", type=int, default=3, help="Total number of training epochs to perform.")
    parser.add_argument(
        "--max_train_steps",
        type=int,
        default=None,
        help="Total number of training steps to perform. If provided, overrides num_train_epochs.",
    )
    parser.add_argument(
        "--gradient_accumulation_steps",
        type=int,
        default=1,
        help="Number of updates steps to accumulate before performing a backward/update pass.",
    )
    parser.add_argument(
        "--lr_scheduler_type",
        type=SchedulerType,
        default="linear",
        help="The scheduler type to use.",
        choices=["linear", "cosine", "cosine_with_restarts", "polynomial", "constant", "constant_with_warmup"],
    )
    parser.add_argument(
        "--num_warmup_steps", type=int, default=1, help="Number of steps for the warmup in the lr scheduler."
    )
    parser.add_argument("--output_dir", type=str, default='./pred/submitission.jsonl', help="Where to find the final predct outcome")
    parser.add_argument("--seed", type=int, default=None, help="A seed for reproducible training.")
    parser.add_argument(
        "--model_type",
        type=str,
        default=None,
        help="Model type to use if training from scratch.",
        choices=MODEL_TYPES,
    )
    parser.add_argument("--push_to_hub", action="store_true", help="Whether or not to push the model to the Hub.")
    parser.add_argument(
        "--hub_model_id", type=str, help="The name of the repository to keep in sync with the local `output_dir`."
    )
    parser.add_argument("--hub_token", type=str, help="The token to use to push to the Model Hub.")
    parser.add_argument(
        "--checkpointing_steps",
        type=str,
        default=None,
        help="Whether the various states should be saved at the end of every n steps, or 'epoch' for each epoch.",
    )
    parser.add_argument(
        "--resume_from_checkpoint",
        type=str,
        default=None,
        help="If the training should continue from a checkpoint folder.",
    )
    parser.add_argument(
        "--with_tracking",
        action="store_true",
        help="Whether to enable experiment trackers for logging.",
    )
    parser.add_argument(
        "--report_to",
        type=str,
        default="all",
        help=(
            'The integration to report the results and logs to. Supported platforms are `"tensorboard"`,'
            ' `"wandb"` and `"comet_ml"`. Use `"all"` (default) to report to all integrations.'
            "Only applicable when `--with_tracking` is passed."
        ),
    )
    # args = parser.parse_args()
    args, unknown = parser.parse_known_args()

    # Sanity checks
    if args.dataset_name is None and args.train_file is None and args.validation_file is None:
        raise ValueError("Need either a dataset name or a training/validation file.")
    else:
        if args.train_file is not None:
            extension = args.train_file.split(".")[-1]
            assert extension in ["csv", "json"], "`train_file` should be a csv or a json file."
        if args.validation_file is not None:
            extension = args.validation_file.split(".")[-1]
            assert extension in ["csv", "json"], "`validation_file` should be a csv or a json file."

    if args.push_to_hub:
        assert args.output_dir is not None, "Need an `output_dir` to create a repo when `--push_to_hub` is passed."

    return args

args = parse_args()

# Sending telemetry. Tracking the example usage helps us better allocate resources to maintain them. The
# information sent is the one passed as arguments along with your Python/PyTorch versions.
send_example_telemetry("run_summarization_no_trainer", args)

# Initialize the accelerator. We will let the accelerator handle device placement for us in this example.
# If we're using tracking, we also need to initialize it here and it will by default pick up all supported trackers
# in the environment
accelerator_log_kwargs = {}

if args.with_tracking:
    accelerator_log_kwargs["log_with"] = args.report_to
    accelerator_log_kwargs["logging_dir"] = args.output_dir

accelerator = Accelerator(gradient_accumulation_steps=args.gradient_accumulation_steps, **accelerator_log_kwargs)
if args.source_prefix is None and args.model_name_or_path in [
    "t5-small",
    "t5-base",
    "t5-large",
    "t5-3b",
    "t5-11b",
]:
    logger.warning(
        "You're running a t5 model but didn't provide a source prefix, which is the expected, e.g. with "
        "`--source_prefix 'summarize: ' `"
    )
# Make one log on every process with the configuration for debugging.
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%m/%d/%Y %H:%M:%S",
    level=logging.INFO,
)
logger.info(accelerator.state, main_process_only=False)
if accelerator.is_local_main_process:
    datasets.utils.logging.set_verbosity_warning()
    transformers.utils.logging.set_verbosity_info()
else:
    datasets.utils.logging.set_verbosity_error()
    transformers.utils.logging.set_verbosity_error()

# If passed along, set the training seed now.
if args.seed is not None:
    set_seed(args.seed)

# Handle the repository creation
if accelerator.is_main_process:
    if args.push_to_hub:
        if args.hub_model_id is None:
            repo_name = get_full_repo_name(Path(args.output_dir).name, token=args.hub_token)
        else:
            repo_name = args.hub_model_id
        repo = Repository(args.output_dir, clone_from=repo_name)

        with open(os.path.join(args.output_dir, ".gitignore"), "w+") as gitignore:
            if "step_*" not in gitignore:
                gitignore.write("step_*\n")
            if "epoch_*" not in gitignore:
                gitignore.write("epoch_*\n")
    elif args.output_dir is not None:
        os.makedirs(args.output_dir, exist_ok=True)
accelerator.wait_for_everyone()

"""# load data"""

def data_format(datas):
  for data in datas:
    data['article'] = data['maintext']
    del data['maintext']
  return datas
with open(args.test_file) as f:
    test_data = [json.loads(line) for line in f.readlines()]

new_test_data = data_format(test_data)
new_test_data = Dataset.from_list(new_test_data)

raw_datasets = datasets.DatasetDict({"test": new_test_data})

# Load pretrained model and tokenizer
#
# In distributed training, the .from_pretrained methods guarantee that only one local process can concurrently
# download model & vocab.
if args.config_name:
    config = AutoConfig.from_pretrained(args.config_name)
elif args.model_name_or_path:
    config = AutoConfig.from_pretrained(args.model_name_or_path)
else:
    config = CONFIG_MAPPING[args.model_type]()
    logger.warning("You are instantiating a new config instance from scratch.")

if args.tokenizer_name:
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_name, use_fast=not args.use_slow_tokenizer)
elif args.model_name_or_path:
    tokenizer = AutoTokenizer.from_pretrained(args.model_name_or_path, use_fast=not args.use_slow_tokenizer)
else:
    raise ValueError(
        "You are instantiating a new tokenizer from scratch. This is not supported by this script."
        "You can do it from another script, save it, and load it from here, using --tokenizer_name."
    )

if args.model_name_or_path:
    model = AutoModelForSeq2SeqLM.from_pretrained(
        args.model_name_or_path,
        from_tf=bool(".ckpt" in args.model_name_or_path),
        config=config,
    )
else:
    logger.info("Training new model from scratch")
    model = AutoModelForSeq2SeqLM.from_config(config)

model.resize_token_embeddings(len(tokenizer))
if model.config.decoder_start_token_id is None:
    raise ValueError("Make sure that `config.decoder_start_token_id` is correctly defined")

prefix = args.source_prefix if args.source_prefix is not None else ""

# Preprocessing the datasets.
# First we tokenize all the texts.
column_names = raw_datasets["test"].column_names

# Get the column names for input/target.
dataset_columns = summarization_name_mapping.get(args.dataset_name, None)
if args.text_column is None:
    text_column = dataset_columns[0] if dataset_columns is not None else column_names[0]
else:
    text_column = args.text_column
    if text_column not in column_names:
        raise ValueError(
            f"--text_column' value '{args.text_column}' needs to be one of: {', '.join(column_names)}"
        )
if args.summary_column is None:
    summary_column = dataset_columns[1] if dataset_columns is not None else column_names[1]
else:
    summary_column = args.summary_column
    if summary_column not in column_names:
        raise ValueError(
            f"--summary_column' value '{args.summary_column}' needs to be one of: {', '.join(column_names)}"
        )

# Temporarily set max_target_length for training.
max_target_length = args.max_target_length
padding = "max_length" if args.pad_to_max_length else False

def preprocess_function(examples):
    inputs = examples[text_column]
    # targets = examples[summary_column]
    inputs = [prefix + inp for inp in inputs]
    model_inputs = tokenizer(inputs, max_length=args.max_source_length, padding=padding, truncation=True)

    # Tokenize targets with the `text_target` keyword argument
    # labels = tokenizer(text_target=targets, max_length=max_target_length, padding=padding, truncation=True)

    # If we are padding here, replace all tokenizer.pad_token_id in the labels by -100 when we want to ignore
    # padding in the loss.
    # if padding == "max_length" and args.ignore_pad_token_for_loss:
    #     labels["input_ids"] = [
    #         [(l if l != tokenizer.pad_token_id else -100) for l in label] for label in labels["input_ids"]
    #     ]

    # model_inputs["labels"] = labels["input_ids"]
    return model_inputs

with accelerator.main_process_first():
    processed_datasets = raw_datasets.map(
        preprocess_function,
        batched=True,
        num_proc=args.preprocessing_num_workers,
        remove_columns=column_names,
        load_from_cache_file=not args.overwrite_cache,
        desc="Running tokenizer on dataset",
    )

# train_dataset = processed_datasets["train"]
# eval_dataset = processed_datasets["validation"]
test_dataset = processed_datasets["test"]

# Log a few random samples from the training set:
for index in random.sample(range(len(test_dataset)), 1):
    logger.info(f"Sample {index} of the training set: {test_dataset[index]}.")

label_pad_token_id = -100 if args.ignore_pad_token_for_loss else tokenizer.pad_token_id
data_collator = DataCollatorForSeq2Seq(
    tokenizer,
    model=model,
    label_pad_token_id=label_pad_token_id,
    pad_to_multiple_of=8 if accelerator.use_fp16 else None,
)

def postprocess_text(preds, labels):
    preds = [pred.strip() for pred in preds]
    labels = [label.strip() for label in labels]

    # rougeLSum expects newline after each sentence
    preds = ["\n".join(nltk.sent_tokenize(pred)) for pred in preds]
    labels = ["\n".join(nltk.sent_tokenize(label)) for label in labels]

    return preds, labels


test_dataloader = DataLoader(test_dataset,
                             collate_fn=data_collator,
                             batch_size=args.per_device_eval_batch_size)

# Prepare everything with our `accelerator`.
model, test_dataloader, = accelerator.prepare(
    model, test_dataloader,
)

def flat_list(l):
  return [item for sublist in l for item in sublist]

pred_list = []
label_list = []

model.eval()
if args.val_max_target_length is None:
    args.val_max_target_length = args.max_target_length

gen_kwargs = {
    "max_length": args.val_max_target_length if args is not None else config.max_length,
    "num_beams": args.num_beams,
    "do_sample": args.do_sample,
    "top_k": args.top_k,
    "top_p": args.top_p,
    "temperature": args.temperature,
    "no_repeat_ngram_size": args.no_repeat_ngram_size,
}
for step, batch in enumerate(test_dataloader):
    with torch.no_grad():
        generated_tokens = accelerator.unwrap_model(model).generate(
            batch["input_ids"],
            attention_mask=batch["attention_mask"],
            **gen_kwargs,
        )

        generated_tokens = accelerator.pad_across_processes(
            generated_tokens, dim=1, pad_index=tokenizer.pad_token_id
        )
        generated_tokens = accelerator.gather_for_metrics((generated_tokens))
        generated_tokens = generated_tokens.cpu().numpy()

        if isinstance(generated_tokens, tuple):
            generated_tokens = generated_tokens[0]
        decoded_preds = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)
        pred_list.append(decoded_preds)

flat_pred = flat_list(pred_list)
pred_df = pd.DataFrame(flat_pred)

# args.output_dir = '../tmp'
# args.output_dir = './'
print(args.output_dir)

outcome_list = []
for i in range(len(flat_pred)):
  outcome_list.append({"title":flat_pred[i], "id": raw_datasets['test'][i]['id']})
try:
  with open(args.output_dir, 'w', encoding='utf-8') as f:
    for data in outcome_list:
      json.dump(data, f)
      f.write("\n")
  print(f'file save in {args.output_dir}')
except:
  with open('b08305056_submit.jsonl', 'w', encoding='utf-8') as f:
    for data in outcome_list:
      json.dump(data, f)
      f.write("\n")
    print('file fail to save in assign path, instead it save in b08305056_submit.jsonl')