TASK=$1
MODEL_NAME=$2
IDX=$3
VM_NAME=$4
TRACE=$5

DELAY=10
BDP_MULTIPLIER=1
DURATION=60

get_vm_ip() {
    sudo virsh domifaddr "$1" | grep -oE '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b' | tr -d ' '
}


PATH_TO_DIR=$PWD/../$TASK/output/$MODEL_NAME/idx$IDX
STATUS_FILE="$PATH_TO_DIR/status.log"

if [[ -s "$STATUS_FILE" ]] && [[ $(cat "$STATUS_FILE") -gt 0 ]]; then
    CODE_IDX=$(cat "$STATUS_FILE")
else
    echo "Status is zero or file is missing."
    exit 1
fi
CODE_IDX=$((CODE_IDX-1))
echo "Using code_idx=$CODE_IDX for idx=$IDX"

PATH_TO_CODE=$PWD/../$TASK/output/$MODEL_NAME/idx$IDX/code$CODE_IDX.txt
if [ ! -f $PATH_TO_CODE ]; then
    echo "File not found!"
    exit 1
fi

vm_ip=$(get_vm_ip $VM_NAME)

if [ -z "$vm_ip" ]; then
    echo "VM is not running or IP address not found."
    exit 1
fi

if [[ $(wc -w <<< "$vm_ip") -ne 1 ]]; then
    echo "Multiple IP addresses found. Expected exactly one."
    exit 1
fi

# if trace exists on current host exit
save_path=$PWD/../$TASK/output/$MODEL_NAME/idx$IDX/code$CODE_IDX/eval/
if [ -f $save_path/$trace_name ]; then
    echo "\t Already run. exiting..."
    exit 1
fi

# copy files over
ssh -o StrictHostKeyChecking=no rohit@$vm_ip "rm -rfv ~/tcp_heuristic/ && mkdir -p ~/tcp_heuristic/"
scp -o StrictHostKeyChecking=no $PWD/../$TASK/* rohit@$vm_ip:~/tcp_heuristic/
scp $PATH_TO_CODE rohit@$vm_ip:~/tcp_heuristic/code.txt

# build and install kmodule
ssh -o StrictHostKeyChecking=no rohit@$vm_ip 'cat ~/tcp_heuristic/tcp_heuristic.template > ~/tcp_heuristic/tcp_heuristic.c; echo "" >> ~/tcp_heuristic/tcp_heuristic.c; cat ~/tcp_heuristic/code.txt >> ~/tcp_heuristic/tcp_heuristic.c'
ssh -o StrictHostKeyChecking=no rohit@$vm_ip "cd ~/tcp_heuristic/ && make clean && make -j"
ssh -o StrictHostKeyChecking=no rohit@$vm_ip "sudo insmod ~/tcp_heuristic/build/tcp_heuristic.ko || sudo dmesg | tail -20"

# copy utils (for LD_PRELOAD) and build them there
ssh -o StrictHostKeyChecking=no rohit@$vm_ip "rm -rfv ~/utils && mkdir -p ~/utils"
scp -o StrictHostKeyChecking=no $PWD/../utils/* rohit@$vm_ip:~/utils/
ssh -o StrictHostKeyChecking=no rohit@$vm_ip "cd ~/utils && make -j"

# copy traces
ssh -o StrictHostKeyChecking=no rohit@$vm_ip "rm -rfv ~/traces && mkdir -p ~/traces"
scp -o StrictHostKeyChecking=no $PWD/sage_traces/traces/* rohit@$vm_ip:~/traces/

trace_name=delay${DELAY}_${TRACE}_${BDP_MULTIPLIER}bdp_dur${DURATION}

# copy over evaluate internal and run it
scp -o StrictHostKeyChecking=no evaluate_vm.sh evaluate_internal.sh rohit@$vm_ip:~/
ssh -o StrictHostKeyChecking=no rohit@$vm_ip "bash ~/evaluate_vm.sh $VM_NAME $DELAY $TRACE $BDP_MULTIPLIER $DURATION"

mkdir -p $save_path
# copy logs once run is done
scp -o StrictHostKeyChecking=no rohit@$vm_ip:~/logs/* $save_path