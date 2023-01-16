# "${1}" is one argument passed to the script, the test file dir
# "${2}" is second argument passed to the script, the output_dir
python sum_pred.py \
--per_device_eval_batch_size 32 \
--num_beams 6 \
--do_sample False \
--test_file "${1}" --output_dir "${2}"