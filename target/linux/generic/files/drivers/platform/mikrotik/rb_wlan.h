/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * MikroTik RouterBoot WLAN calibration data helpers.
 */

#ifndef _ROUTERBOOT_WLAN_H_
#define _ROUTERBOOT_WLAN_H_

#include <linux/types.h>

#define RB_WLAN_ERD_ID_SOLO		0x0001
#define RB_WLAN_ERD_ID_MULTI_8001	0x8001
#define RB_WLAN_ERD_ID_MULTI_8201	0x8201

int rb_wlan_data_unpack(const u8 *inbuf, size_t inlen, const u16 tag_id,
			void *outbuf, size_t *outlen);

#endif /* _ROUTERBOOT_WLAN_H_ */
