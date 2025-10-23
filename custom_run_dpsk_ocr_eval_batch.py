import os
import re
import argparse
from tqdm import tqdm
import torch
if torch.version.cuda == '11.8':
    os.environ["TRITON_PTXAS_PATH"] = "/usr/local/cuda-11.8/bin/ptxas"
os.environ['VLLM_USE_V1'] = '0'
os.environ["CUDA_VISIBLE_DEVICES"] = '0'

from config import MODEL_PATH, INPUT_PATH, OUTPUT_PATH, PROMPT, MAX_CONCURRENCY, CROP_MODE, NUM_WORKERS
from concurrent.futures import ThreadPoolExecutor
import glob
from PIL import Image
from deepseek_ocr import DeepseekOCRForCausalLM

from vllm.model_executor.models.registry import ModelRegistry

from vllm import LLM, SamplingParams
from process.ngram_norepeat import NoRepeatNGramLogitsProcessor
from process.image_process import DeepseekOCRProcessor
ModelRegistry.register_model("DeepseekOCRForCausalLM", DeepseekOCRForCausalLM)


llm = LLM(
    model=MODEL_PATH,
    hf_overrides={"architectures": ["DeepseekOCRForCausalLM"]},
    block_size=256,
    enforce_eager=False,
    trust_remote_code=True, 
    max_model_len=8192,
    swap_space=0,
    max_num_seqs = MAX_CONCURRENCY,
    tensor_parallel_size=1,
    gpu_memory_utilization=0.9,
)

logits_processors = [NoRepeatNGramLogitsProcessor(ngram_size=40, window_size=90, whitelist_token_ids= {128821, 128822})] #window for fast；whitelist_token_ids: <td>,</td>

sampling_params = SamplingParams(
    temperature=0.0,
    max_tokens=8192,
    logits_processors=logits_processors,
    skip_special_tokens=False,
)

class Colors:
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    RESET = '\033[0m' 

def clean_formula(text):

    formula_pattern = r'\\\[(.*?)\\\]'
    
    def process_formula(match):
        formula = match.group(1)

        formula = re.sub(r'\\quad\s*\([^)]*\)', '', formula)
        
        formula = formula.strip()
        
        return r'\[' + formula + r'\]'

    cleaned_text = re.sub(formula_pattern, process_formula, text)
    
    return cleaned_text

def re_match(text):
    pattern = r'(<\|ref\|>(.*?)<\|/ref\|><\|det\|>(.*?)<\|/det\|>)'
    matches = re.findall(pattern, text, re.DOTALL)


    # mathes_image = []
    mathes_other = []
    for a_match in matches:
        mathes_other.append(a_match[0])
    return matches, mathes_other

def process_single_image(image, prompt):
    """single image"""
    prompt_in = prompt
    cache_item = {
        "prompt": prompt_in,
        "multi_modal_data": {"image": DeepseekOCRProcessor().tokenize_with_images(images = [image], bos=True, eos=True, cropping=CROP_MODE)},
    }
    return cache_item


def main():
    parser = argparse.ArgumentParser(description='Process batch of images with DeepSeek OCR using custom prompt')
    parser.add_argument('--prompt', type=str, help='Custom prompt to use for OCR (overrides default from config)')
    parser.add_argument('--input', type=str, default=INPUT_PATH, help='Input directory path containing images')
    parser.add_argument('--output', type=str, default=OUTPUT_PATH, help='Output directory path')
    
    args = parser.parse_args()
    
    # Use custom prompt if provided, otherwise use default from config
    prompt = args.prompt if args.prompt else PROMPT
    
    print(f"{Colors.BLUE}Using prompt: {prompt}{Colors.RESET}")
    
    # Set paths from arguments if provided
    if args.input:
        global INPUT_PATH
        INPUT_PATH = args.input
    if args.output:
        global OUTPUT_PATH
        OUTPUT_PATH = args.output

    # INPUT_PATH = OmniDocBench images path

    os.makedirs(OUTPUT_PATH, exist_ok=True)

    # print('image processing until processing prompts.....')

    print(f'{Colors.RED}glob images.....{Colors.RESET}')

    images_path = glob.glob(f'{INPUT_PATH}/*')

    images = []

    for image_path in images_path:
        image = Image.open(image_path).convert('RGB')
        images.append(image)

    # batch_inputs = []


    # for image in tqdm(images):

    #     prompt_in = prompt
    #     cache_list = [
    #         {
    #             "prompt": prompt_in,
    #             "multi_modal_data": {"image": Image.open(image).convert('RGB')},
    #         }
    #     ]
    #     batch_inputs.extend(cache_list)

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:  
        batch_inputs = list(tqdm(
            executor.map(lambda img: process_single_image(img, prompt), images),
            total=len(images),
            desc="Pre-processed images"
        ))


    

    outputs_list = llm.generate(
        batch_inputs,
        sampling_params=sampling_params
    )


    output_path = OUTPUT_PATH

    os.makedirs(output_path, exist_ok=True)

    for output, image in zip(outputs_list, images_path):

        content = output.outputs[0].text
        mmd_det_path = output_path + image.split('/')[-1].replace('.jpg', '_det.md')

        with open(mmd_det_path, 'w', encoding = 'utf-8') as afile:
            afile.write(content)

        content = clean_formula(content)
        matches_ref, mathes_other = re_match(content)
        for idx, a_match_other in enumerate(tqdm(mathes_other, desc="other")):
            content = content.replace(a_match_other, '').replace('\n\n\n\n', '\n\n').replace('\n\n\n', '\n\n').replace('<center>', '').replace('</center>', '')
        
        mmd_path = output_path + image.split('/')[-1].replace('.jpg', '.md')

        with open(mmd_path, 'w', encoding = 'utf-8') as afile:
            afile.write(content)


if __name__ == "__main__":
    main()