// SPDX-License-Identifier: GPL-2.0-only
/*
 * NVMEM layout driver for MikroTik Routerboard hard config cells
 *
 * Copyright (C) 2024 Robert Marko <robimarko@gmail.com>
 * Based on the sysfs hard config driver by Thibaut VARÈNE <hacks+kernel@slashdirt.org>
 * Comments documenting the format carried over from routerboot.c
 */

#include <linux/bitfield.h>
#include <linux/etherdevice.h>
#include <linux/mod_devicetable.h>
#include <linux/nvmem-consumer.h>
#include <linux/nvmem-provider.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/slab.h>

#include "rb_hardconfig.h"
#include "routerboot.h"
#include "rb_wlan.h"

#define TLV_TAG_MASK 	GENMASK(15, 0)
#define TLV_LEN_MASK 	GENMASK(31, 16)

struct rb_wlan_cell {
	u16 erd_tag_id;
	u16 raw_len;
};

static const char *rb_tlv_cell_name(u16 tag)
{
	switch (tag) {
	case RB_ID_FLASH_INFO:
		return "flash-info";
	case RB_ID_MAC_ADDRESS_PACK:
		return "base-mac-address";
	case RB_ID_BOARD_PRODUCT_CODE:
		return "board-product-code";
	case RB_ID_BIOS_VERSION:
		return "booter-version";
	case RB_ID_SERIAL_NUMBER:
		return "board-serial";
	case RB_ID_MEMORY_SIZE:
		return "mem-size";
	case RB_ID_MAC_ADDRESS_COUNT:
		return "mac-count";
	case RB_ID_HW_OPTIONS:
		return "hw-options";
	case RB_ID_WLAN_DATA:
		return "wlan-data";
	case RB_ID_BOARD_IDENTIFIER:
		return "board-identifier";
	case RB_ID_PRODUCT_NAME:
		return "product-name";
	case RB_ID_DEFCONF:
		return "defconf";
	case RB_ID_BOARD_REVISION:
		return "board-revision";
	default:
		break;
	}

	return NULL;
}

static int rb_tlv_mac_read_cb(void *priv, const char *id, int index,
			      unsigned int offset, void *buf,
			      size_t bytes)
{
	if (index < 0)
		return -EINVAL;

	if (!is_valid_ether_addr(buf))
		return -EINVAL;

	eth_addr_add(buf, index);

	return 0;
}

static int rb_wlan_read_cb(void *priv, const char *id, int index,
			   unsigned int offset, void *buf, size_t bytes)
{
	struct rb_wlan_cell *wlan_cell = priv;
	size_t outlen = RB_ART_SIZE;
	u8 *outbuf;
	int ret;

	outbuf = kmalloc(outlen, GFP_KERNEL);
	if (!outbuf)
		return -ENOMEM;

	ret = rb_wlan_data_unpack(buf, wlan_cell->raw_len,
				  wlan_cell->erd_tag_id, outbuf, &outlen);
	if (ret)
		goto out;

	memset(buf, 0, RB_ART_SIZE);
	memcpy(buf, outbuf, outlen);

out:
	kfree(outbuf);
	return ret;
}

static nvmem_cell_post_process_t rb_tlv_read_cb(u16 tag)
{
	switch (tag) {
	case RB_ID_MAC_ADDRESS_PACK:
		return &rb_tlv_mac_read_cb;
	case RB_ID_WLAN_DATA:
		return &rb_wlan_read_cb;
	default:
		break;
	}

	return NULL;
}

static int rb_add_wlan_cell(struct device *dev, struct nvmem_device *nvmem,
			    struct device_node *layout, const char *name,
			    u32 offset, u16 tlv_len, u16 erd_tag_id)
{
	struct nvmem_cell_info cell = {};
	struct rb_wlan_cell *wlan_cell;

	wlan_cell = devm_kzalloc(dev, sizeof(*wlan_cell), GFP_KERNEL);
	if (!wlan_cell)
		return -ENOMEM;

	wlan_cell->erd_tag_id = erd_tag_id;
	wlan_cell->raw_len = tlv_len;

	cell.name = name;
	cell.offset = offset;
	cell.raw_len = tlv_len;
	cell.bytes = RB_ART_SIZE;
	cell.np = of_get_child_by_name(layout, cell.name);
	cell.read_post_process = rb_wlan_read_cb;
	cell.priv = wlan_cell;

	return nvmem_add_one_cell(nvmem, &cell);
}

static int rb_add_wlan_cells(struct device *dev, struct nvmem_device *nvmem,
			     struct device_node *layout, const u8 *data,
			     u32 offset, u16 tlv_len)
{
	static const struct {
		const char *name;
		u16 erd_tag_id;
	} multi[] = {
		{ "wlan-data-0", RB_WLAN_ERD_ID_MULTI_8001 },
		{ "wlan-data-2", RB_WLAN_ERD_ID_MULTI_8201 },
	};
	u8 *outbuf;
	size_t outlen;
	int i, ret, err = 0;

	if (tlv_len > RB_ART_SIZE)
		return -EFBIG;

	outbuf = kmalloc(RB_ART_SIZE, GFP_KERNEL);
	if (!outbuf)
		return -ENOMEM;

	outlen = RB_ART_SIZE;
	ret = rb_wlan_data_unpack(data + offset, tlv_len, RB_WLAN_ERD_ID_SOLO,
				  outbuf, &outlen);
	if (!ret) {
		kfree(outbuf);
		return rb_add_wlan_cell(dev, nvmem, layout, "wlan-data",
					offset, tlv_len, RB_WLAN_ERD_ID_SOLO);
	}

	for (i = 0; i < ARRAY_SIZE(multi); i++) {
		outlen = RB_ART_SIZE;
		ret = rb_wlan_data_unpack(data + offset, tlv_len,
					  multi[i].erd_tag_id, outbuf, &outlen);
		if (ret)
			continue;

		ret = rb_add_wlan_cell(dev, nvmem, layout, multi[i].name,
				       offset, tlv_len, multi[i].erd_tag_id);
		if (ret) {
			err = ret;
			break;
		}
	}

	kfree(outbuf);

	return err;
}

static int rb_add_cells(struct device *dev, struct nvmem_device *nvmem,
			const size_t data_len, u8 *data)
{
	u32 node, offset = sizeof(RB_MAGIC_HARD);
	struct nvmem_cell_info cell = {};
	struct device_node *layout;
	u16 tlv_tag, tlv_len;
	int ret;

	layout = of_nvmem_layout_get_container(nvmem);
	if (!layout)
		return -ENOENT;

	/*
	 * Routerboot tag nodes are u32 values:
	 * - The low nibble is the tag identification number,
	 * - The high nibble is the tag payload length (node excluded) in bytes.
	 * Tag nodes are CPU-endian.
	 * Tag nodes are 32bit-aligned.
	 *
	 * The payload immediately follows the tag node.
	 * Payload offset will always be aligned. while length may not end on 32bit
	 * boundary (the only known case is when parsing ERD data).
	 * The payload is CPU-endian when applicable.
	 * Tag nodes are not ordered (by ID) on flash.
	 */
	while ((offset + sizeof(node)) <= data_len) {
		node = *((const u32 *) (data + offset));
		/* Tag list ends with null node */
		if (!node)
			break;

		tlv_tag = FIELD_GET(TLV_TAG_MASK, node);
		tlv_len = FIELD_GET(TLV_LEN_MASK, node);

		offset += sizeof(node);
		if (offset + tlv_len > data_len) {
			dev_err(dev, "Out of bounds field (0x%x bytes at 0x%x)\n",
			        tlv_len, offset);
			break;
		}

		cell.name = rb_tlv_cell_name(tlv_tag);
		if (!cell.name)
			goto skip;

		if (tlv_tag == RB_ID_WLAN_DATA) {
			ret = rb_add_wlan_cells(dev, nvmem, layout, data,
						offset, tlv_len);
			if (ret) {
				of_node_put(layout);
				return ret;
			}

			goto skip;
		}

		cell.offset = offset;
		/*
		 * MikroTik stores MAC-s with length of 8 bytes,
		 * but kernel expects it to be ETH_ALEN (6 bytes),
		 * so we need to make sure that is the case.
		 */
		if (tlv_tag == RB_ID_MAC_ADDRESS_PACK)
			cell.bytes = ETH_ALEN;
		else
			cell.bytes = tlv_len;
		cell.np = of_get_child_by_name(layout, cell.name);
		cell.read_post_process = rb_tlv_read_cb(tlv_tag);

		ret = nvmem_add_one_cell(nvmem, &cell);
		if (ret) {
			of_node_put(layout);
			return ret;
		}

		/*
		 * The only known situation where len may not end on 32bit
		 * boundary is within ERD data. Since we're only extracting
		 * one tag (the first and only one) from that data, we should
		 * never need to forcefully ALIGN(). Do it anyway, this is not a
		 * performance path.
		 */
skip:
		offset += ALIGN(tlv_len, sizeof(offset));
	}

	of_node_put(layout);

	return 0;
}

static int rb_parse_table(struct nvmem_layout *layout)
{
	struct nvmem_device *nvmem = layout->nvmem;
	struct device *dev = &layout->dev;
	size_t mtd_size;
	u8 *data;
	u32 hdr;
	int ret;

	ret = nvmem_device_read(nvmem, 0, sizeof(hdr), &hdr);
	if (ret < 0)
		return ret;

	if (hdr != RB_MAGIC_HARD) {
		dev_err(dev, "Invalid header\n");
		return -EINVAL;
	}

	mtd_size = nvmem_dev_size(nvmem);

	data = devm_kmalloc(dev, mtd_size, GFP_KERNEL);
	if (!data)
		return -ENOMEM;

	ret = nvmem_device_read(nvmem, 0, mtd_size, data);
	if (ret != mtd_size)
		return ret;

	return rb_add_cells(dev, nvmem, mtd_size, data);
}

static int rb_nvmem_probe(struct nvmem_layout *layout)
{
	layout->add_cells = rb_parse_table;

	return nvmem_layout_register(layout);
}

static void rb_nvmem_remove(struct nvmem_layout *layout)
{
	nvmem_layout_unregister(layout);
}

static const struct of_device_id rb_nvmem_of_match_table[] = {
	{ .compatible = "mikrotik,routerboot-nvmem", },
	{},
};
MODULE_DEVICE_TABLE(of, rb_nvmem_of_match_table);

static struct nvmem_layout_driver rb_nvmem_layout = {
	.probe = rb_nvmem_probe,
	.remove = rb_nvmem_remove,
	.driver = {
		.owner = THIS_MODULE,
		.name = "rb_nvmem",
		.of_match_table = rb_nvmem_of_match_table,
	},
};
module_nvmem_layout_driver(rb_nvmem_layout);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Robert Marko <robimarko@gmail.com>");
MODULE_DESCRIPTION("NVMEM layout driver for MikroTik Routerboard hard config cells");
