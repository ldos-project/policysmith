source /home/ardula/dumbsearch/vm_utilities.sh

vm_rm vm1

for idx in {0..99}; do
    for trace in ATT-LTE-driving-2016.down TMobile-LTE-short.down Verizon-LTE-short.down; do
        echo "[run_eval] ################## idx=$idx, trace=$trace ##################"
        vm_create
        vm_refresh_ips
        sleep 1
        bash evaluate.sh kern_mod gemini-2.0-flash $idx vm1 $trace
        vm_rm vm1
    done
done