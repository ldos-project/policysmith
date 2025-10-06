#ifndef BPF_MAP_HACK_HEADER
#define BPF_MAP_HACK_HEADER

#include <linux/fs.h> 		/* Needed for ioctl api */
#include <linux/bpf.h>		/* Needed to get the ebpf_map */
#include <linux/cdev.h>		/* Needed for cdev functions */
#include <linux/device.h>	/* Needed for device_create */
#include <linux/uaccess.h>	/* Needed for copy_from_user */
#include <linux/printk.h>	/* Needed for pr_info() */

static dev_t dev = 0;                       // (MIRRORS: `dev` in fstore.c)
static struct cdev cwnd_cdev;                // (MIRRORS: `fstore_cdev` in fstore.c)
static struct class *dev_class;              // (MIRRORS: `dev_class` in fstore.c)
struct bpf_map *cwnd_map = NULL;             // (REPLACES: `fstore_map` hash table) 

enum cwnd_store_cmd {
    REGISTER_CWND = 0x0,
    UNREGISTER_CWND = 0x1,
};

static long cwnd_ioctl(struct file *file,
	unsigned int cmd,
	unsigned long data)
{
	int err = 0;
	int fd;
	struct bpf_map *map;

	switch(cmd) {
		case REGISTER_CWND:
			if (copy_from_user(&fd, (int __user *)data, sizeof(fd))) {
				pr_err("cwnd_store: Copying fd from user failed\n");
				err = -EINVAL;
				break;
			}

			map = bpf_map_get(fd);
			if (IS_ERR(map)) {
				pr_err("cwnd_store: bpf_map_get failed\n");
				err = PTR_ERR(map);
				break;
			}

			if (cwnd_map) bpf_map_put(cwnd_map);
			cwnd_map = map;
			pr_info("cwnd_store: Map registered successfully\n");
			break;

		case UNREGISTER_CWND:
			if (cwnd_map) {
				bpf_map_put(cwnd_map);
				cwnd_map = NULL;
				pr_info("cwnd_store: Map unregistered successfully\n");
			}
			break;

		default:
			pr_info("cwnd_store: Unknown ioctl command %u\n", cmd);
			err = -EINVAL;
	}
	return err;
}

static struct file_operations fops = {
	.owner = THIS_MODULE,
	.read = NULL,
	.write = NULL,
	.open = NULL,
	.unlocked_ioctl = cwnd_ioctl,
	.release = NULL,
};

int init_hack(void);
int init_hack(void)
{
	/* Allocating Major number */
	if ((alloc_chrdev_region(&dev, 0, 1, "cwnd_dev")) < 0) {
		pr_err("cwnd_store: Cannot allocate major number\n");
		return -1;
	}

	pr_info("cwnd_store: Major = %d Minor = %d\n", MAJOR(dev), MINOR(dev));

	/* Creating cdev structure */
	cdev_init(&cwnd_cdev, &fops);

	/* Adding character device to the system */
	if ((cdev_add(&cwnd_cdev, dev, 1)) < 0) {
		pr_err("cwnd_store: Cannot add the device to the system\n");
		goto r_class;
	}

	/* Creating struct class */
	if (IS_ERR(dev_class = class_create("cwnd_class"))) {
		pr_err("cwnd_store: Cannot create the struct class\n");
		goto r_class;
	}

	/* Creating device */
	if (IS_ERR(device_create(dev_class, NULL, dev, NULL, "cwnd_device"))) {
		pr_err("cwnd_store: Cannot create the Device\n");
		goto r_device;
	}

	pr_info("cwnd_store: Device created successfully\n");
	return 0;

r_device:
	class_destroy(dev_class);
r_class:
	unregister_chrdev_region(dev, 1);
	return -1;
}

void destroy_hack(void);
void destroy_hack(void)
{
	/* Cleanup map if still registered */
	if (cwnd_map) {
		bpf_map_put(cwnd_map);
		cwnd_map = NULL;
	}

	/* Cleanup device */
	device_destroy(dev_class, dev);
	class_destroy(dev_class);
	cdev_del(&cwnd_cdev);
	unregister_chrdev_region(dev, 1);

	pr_info("cwnd_store: Device unloaded\n");
}

static bool lookup_cwnd(u32 *out)
{
	u32 key = 0;
	void *value;
	if (!cwnd_map) return false;

	// rcu_read_lock();
	value = cwnd_map->ops->map_lookup_elem(cwnd_map, &key);
	// rcu_read_unlock();

	if (!value) return false;

	*out = *(u32*)value;
	return true;
}


#endif