vm_create() {
    # Find lowest available VM number
    i=1
    while sudo virsh list --all --name | grep -q "vm$i"; do
        i=$((i+1))
    done

    new_vm_name="vm$i"
    VM_BASE_IMG=/var/lib/libvirt/images/base_linux68.qcow2
    vm_image="/var/lib/libvirt/images/$new_vm_name.qcow2"

    # Create overlay disk
    sudo qemu-img create -f qcow2 -F qcow2 -b "$VM_BASE_IMG" "$vm_image" > /dev/null 2>&1

    # Install VM
    sudo virt-install \
        --name "$new_vm_name" \
        --memory 3072 \
        --vcpus 2 \
        --disk path="$vm_image",format=qcow2 \
        --os-variant ubuntu24.04 \
        --network network=default,model=virtio \
        --graphics none \
        --console pty,target_type=serial \
        --import \
        --noautoconsole > /dev/null 2>&1

    echo "VM $new_vm_name created successfully!"
    sleep 2
    max_attempts=10
    attempt=1

    while (( attempt <= max_attempts )); do
        output=$(sudo virsh qemu-agent-command "$new_vm_name" '{
            "execute":"guest-exec",
            "arguments":{
                "path":"/usr/bin/sudo",
                "arg":["sysctl","-w","net.ipv4.ip_forward=1"],
                "capture-output":true
            }
        }' 2>&1)

        if [[ "$output" != *"QEMU guest agent is not connected"* ]]; then
            echo "$output"
            break
        fi

        echo "Attempt $attempt: Guest agent not responding. Retrying..."
        ((attempt++))
        sleep 2
    done

    if (( attempt > max_attempts )); then
        echo "Failed: Guest agent did not respond after $max_attempts attempts."
    fi
}

vm_rm() {
    sudo virsh destroy "$1" > /dev/null 2>&1
    sudo virsh undefine --remove-all-storage "$1" > /dev/null 2>&1
    echo "VM $1 removed successfully!"
}

alias vm_ls="sudo virsh list --all"
alias vm_start="sudo virsh start"
alias vm_bash="sudo virsh console"

vm_ip() {
    sudo virsh domifaddr "$1" | grep -oE '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b' | tr -d ' '
}

vm_refresh_ips() {
    vms=$(sudo virsh list --all | awk '$3 == "running" {print $2}')

    for vm in $vms; do
        ip_info=$(vm_ip "$vm" | awk 'NR>2 {print $4}')
        if [ -z "$ip_info" ]; then
            echo "VM $vm has no IP. Sending dhclient command via qemu-guest-agent..."

            sudo virsh qemu-agent-command "$vm" '{
                "execute":"guest-exec",
                "arguments":{
                    "path":"/usr/bin/sudo",
                    "arg":["dhclient","-v","enp1s0"],
                    "capture-output":true
                }
            }' >/dev/null
        else
            echo "VM $vm already has IP: $ip_info"
        fi
    done
}
