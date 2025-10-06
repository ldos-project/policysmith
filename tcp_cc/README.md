# Setting up VMs
1. Install base VM

```bash
sudo apt-get update
sudo apt install -y qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils virt-manager

# ISO 
VM_ISO_PATH=/var/lib/libvirt/images/ubuntu-24.04.2-live-server-amd64.iso
VM_BASE_IMG=/var/lib/libvirt/images/base_linux68.qcow2
sudo wget -O $VM_ISO_PATH https://old-releases.ubuntu.com/releases/24.04/ubuntu-24.04.2-live-server-amd64.iso
sudo qemu-img create -f qcow2 $VM_BASE_IMG 20G
virt-install --name linux68-base --memory 2048 --vcpus 2 --disk path=$VM_BASE_IMG --cdrom $VM_ISO_PATH --os-variant ubuntu24.04 --network network=default,model=virtio --graphics vnc,listen=0.0.0.0
```

If you are installing the base VM on a machine with no monitor, a VNC server will be created. Connect to the VNC server on Port 5900 and finish the Ubuntu installation instructions.

2. Inside the VM, install mahimahi 
```bash
# basics - no passwords
sudo sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT=.*/GRUB_CMDLINE_LINUX_DEFAULT="console=ttyS0,115200n8 console=tty0"/' /etc/default/grub
sudo update-grub
sudo passwd -d "$USER"
echo "$USER ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/99_$USER
sudo chmod 440 /etc/sudoers.d/99_rohit

# make sure to copy over your ssh public key to authorized_keys before rebooting
sudo reboot

sudo apt-get update
sudo apt-get upgrade
sudo apt-get install protobuf-compiler libprotobuf-dev autotools-dev dh-autoreconf iptables pkg-config dnsmasq-base apache2-bin apache2-dev debhelper libssl-dev ssl-cert  libxcb-present-dev libcairo2-dev  libpango1.0-dev
sudo apt install qemu-guest-agent
sudo apt install iperf3 ifconfig

git clone https://github.com/ravinet/mahimahi
cd mahimahi
./autogen.sh
./configure
make
sudo make install
sudo sysctl -w net.ipv4.ip_forward=1
```

3. Kill the VM once installation is done using `sudo virsh destroy linux68-base`.

4. You might want to add some helper functions / aliases from `vm_utilities.sh` to your `.bashrc` (or just source the whole file).

5. To edit the base image:
```bash
sudo virsh start linux68-base
vm_bash linux68-base
# install stuff
sudo virsh destroy linux68-base
```
