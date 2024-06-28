
import os
import json
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    HfArgumentParser,
    TrainingArguments,
    pipeline,
    logging,
)
from peft import LoraConfig, PeftModel
from trl import SFTTrainer
from pathlib import Path
import pandas as pd




d = load_dataset("gretelai/synthetic_text_to_sql")

d_dataframe = pd.DataFrame(d["train"])

d_dataframe.head()

from datasets import load_dataset
from pathlib import Path
import json

def formatting_sql_data(data_dir='/content/drive/MyDrive/data_sql'):
  data = load_dataset("gretelai/synthetic_text_to_sql")
  dataset_split = {"train": data['train'].shuffle(seed=42).select(range(10000))}

  out_path = Path(data_dir)
  out_path.parent.mkdir(parents=True, exist_ok=True)

  for key, ds in dataset_split.items():
      with open(out_path, "w") as f:
          for item in ds:
              newitem = {
                  "input": item["sql_prompt"],
                  "context": item["sql_context"],
                  "output": item["sql"],
              }
              f.write(json.dumps(newitem) + "\n")

formatting_sql_data(data_dir='/content/drive/MyDrive/data_sql')

def save_json(data_dicts, out_path):
  with open(out_path, 'w') as f:
    for data_dict in data_dicts:
      f.write(json.dumps(data_dict) + "\n")

data = load_dataset("json", data_files="/content/drive/MyDrive/data_sql")
# len(data["train"])

train_data  = data["train"].train_test_split(train_size = 0.95, test_size = 0.05, seed=42, shuffle=True)

raw_train_data = train_data['train']
raw_test_data = train_data['test']

# save_json(raw_train_data, "raw_train_data.json")
# save_json(raw_test_data, "raw_test_data.json")

raw_test_data

raw_train_data[23]



from unsloth import FastLanguageModel
max_seq_length = 2048 # Choose any! We auto support RoPE Scaling internally!
dtype = None # None for auto detection. Float16 for Tesla T4, V100, Bfloat16 for Ampere+
load_in_4bit = True # Use 4bit quantization to reduce memory usage. Can be False.


model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/llama-3-8b-bnb-4bit",
    max_seq_length = max_seq_length,
    dtype = dtype,
    load_in_4bit = load_in_4bit,
)



def generate_prompt_messages(input, context, dialect='mysql', output=''):
  prompt_template = """### Instruction:
  You are a powerful text-to-SQL model. Your job is to answer questions about a database. You are given a question and context regarding one or more tables.
  You must output the SQL query that answers the question.

  ### Dialect:
  {}

  ### Input:
  {}

  ### Context:
  {}

  ### Response:
  {}
  """
  return prompt_template.format(
      dialect,
      input,
      context,
      output
  )


def generate_prompt(example):

  if "output" in list(example.keys()):
    output = example['output']
  else:
    output = ''

  full_prompt = generate_prompt_messages(
                example['input'],
                example['context'],
                dialect='mysql',
                output = output
  )

  return {"text": full_prompt}

train_prompt_data = raw_train_data.map(generate_prompt)

train_prompt_data = train_prompt_data.remove_columns(["input", "context", "output"])

train_prompt_data[3232]["text"]

model = FastLanguageModel.get_peft_model(
    model,
    r = 32, # Choose any number > 0 ! Suggested 8, 16, 32, 64, 128
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj",],
    lora_alpha = 16,
    lora_dropout = 0, # Supports any, but = 0 is optimized
    bias = "none",    # Supports any, but = "none" is optimized
    use_gradient_checkpointing = "unsloth",
    random_state = 3407,
    use_rslora = False,  # support rank stabilized LoRA
    loftq_config = None, # And LoftQ
)

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = train_prompt_data,
    dataset_text_field = "text",
    max_seq_length = max_seq_length,
    dataset_num_proc = 2,
    packing = False, # Can make training 5x faster for short sequences.
    args = TrainingArguments(
        per_device_train_batch_size = 4,
        gradient_accumulation_steps = 4,
        warmup_steps = 5,
        max_steps = 250,
        num_train_epochs =1,
        learning_rate = 2e-4,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        logging_steps = 10,
        optim = "adamw_8bit",
        weight_decay = 0.01,
        lr_scheduler_type = "cosine",
        seed = 3407,
        output_dir = "/content/drive/MyDrive/text_to_sql_2/outputs",
    ),
)

trainer_stats = trainer.train()

model.save_pretrained("/content/drive/MyDrive/text_to_sql_2") # Local saving

# load and inference

max_seq_length = 2048 # Choose any! We auto support RoPE Scaling internally!
dtype = None # None for auto detection. Float16 for Tesla T4, V100, Bfloat16 for Ampere+
load_in_4bit = True # Use 4bit quantization to reduce memory usage. Can be False.

if True:
    from unsloth import FastLanguageModel
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name = "/content/drive/MyDrive/text_to_sql_2", # YOUR MODEL YOU USED FOR TRAINING
        max_seq_length = max_seq_length,
        dtype = dtype,
        load_in_4bit = load_in_4bit,
    )
    FastLanguageModel.for_inference(model)

raw_test_data_output = raw_test_data["output"]

raw_test_data_output[0]

raw_test_data = raw_test_data.remove_columns(["output"])

test_prompt_data = raw_test_data.map(generate_prompt)

test_prompt_data

test_prompt_data =test_prompt_data.remove_columns(["input", "context"])

test_prompt_data[457]["text"]

# FastLanguageModel.for_inference(model)
inputs = tokenizer(test_prompt_data[56]["text"], return_tensors = "pt").to("cuda")

outputs = model.generate(**inputs, max_new_tokens = 128, use_cache = True)
response = tokenizer.batch_decode(outputs)
response[0].rpartition('### Response:')[-1]

response[0].rpartition('### Response:')[-1]

raw_test_data_output[457]

# model output 457
'''SELECT campaign_name, SUM(donation_amount) as total_donations FROM donations JOIN campaigns ON
donations.campaign_id = campaigns.id WHERE campaign_end_date >= '2022-01-01' AND campaign_end_date < '2023-01-01'
GROUP BY campaign_name ORDER BY total_donations DESC LIMIT 3'''

test_prompt_data[259]

raw_test_data_output[259]

# model output 259
"""SELECT AVG(cost) FROM InfrastructureProjects WHERE region = 'Pacific' AND completion_date >= '2016-01-01"""

raw_test_data_output[56], test_prompt_data[56]

# model output 56
'''SELECT MAX(order_quantity) FROM order_quantities WHERE material LIKE '%Recycled Material%''''