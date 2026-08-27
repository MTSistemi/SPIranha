/**
 * Copyright (C) 2021, Mate Kukri <km@mkukri.xyz>
 * Copyright (C) 2023, 2024, Riku Viitanen <riku.viitanen@protonmail.com>
 * Based on "pico-serprog" by Thomas Roth <code@stacksmashing.net>
 * 
 * Licensed under GPLv3
 *
 * Also based on stm32-vserprog:
 *  https://github.com/dword1511/stm32-vserprog
 */

#define DESCRIPTION "SPI flash chip programmer using Flashprog's serprog protocol"
#define WEBSITE "https://codeberg.org/Riku_V/pico-serprog/"

#include "pico/stdlib.h"
#include "pico/binary_info.h"
#include "hardware/spi.h"
#include "tusb.h"
#include "serprog.h"

#define CDC_ITF     0           /* USB CDC interface no */

#define SPI_IF      spi0        /* Which PL022 to use   */
#define SPI_CS_0    5		/* The default CS pin   */
#define SPI_MISO    4
#define SPI_MOSI    3
#define SPI_SCK     2

uint8_t spi_enabled = 0;
uint cs_pin = SPI_CS_0;
#define NUM_CS_AVAILABLE 4	/* Number of usable chip selects */

uint baud = 12000000; /* Default to 12MHz */

static const char progname[16] = "pico-serprog";

/* Map of supported serprog commands */
static const uint32_t cmdmap[8] = {
	(1 << S_CMD_NOP)         |
	(1 << S_CMD_Q_IFACE)     |
	(1 << S_CMD_Q_CMDMAP)    |
	(1 << S_CMD_Q_PGMNAME)   |
	(1 << S_CMD_Q_SERBUF)    |
	(1 << S_CMD_Q_BUSTYPE)   |
	(1 << S_CMD_SYNCNOP)     |
	(1 << S_CMD_O_SPIOP)     |
	(1 << S_CMD_S_BUSTYPE)   |
	(1 << S_CMD_S_SPI_FREQ)  |
	(1 << S_CMD_S_PIN_STATE) |
	(1 << S_CMD_S_SPI_CS)
};


static void use_cs(uint pin) {
	gpio_put(pin, 1);
	gpio_set_dir(pin, GPIO_OUT);
	gpio_set_drive_strength(pin, GPIO_DRIVE_STRENGTH_12MA);
}

static void pullup_cs(uint pin) {
	gpio_set_dir(pin, GPIO_IN);
	gpio_pull_up(pin);
}

static void enable_spi() {
#ifdef PICO_DEFAULT_LED_PIN
	/* Setup status LED */
	gpio_init(PICO_DEFAULT_LED_PIN);
	gpio_set_dir(PICO_DEFAULT_LED_PIN, GPIO_OUT);
#endif

	/* Setup default CS as output, others as inputs with pull-ups */
	for (uint8_t i = SPI_CS_0+1; i<SPI_CS_0+NUM_CS_AVAILABLE; i++) {
	    gpio_init(i);
	    pullup_cs(i);
	}
	gpio_init(cs_pin);
	use_cs(cs_pin);

	/* Setup PL022 */
	spi_init(SPI_IF, baud);
	gpio_set_function(SPI_MISO, GPIO_FUNC_SPI);
	gpio_set_function(SPI_MOSI, GPIO_FUNC_SPI);
	gpio_set_function(SPI_SCK,  GPIO_FUNC_SPI);

	gpio_set_drive_strength(SPI_MISO, GPIO_DRIVE_STRENGTH_12MA);
	gpio_set_drive_strength(SPI_MOSI, GPIO_DRIVE_STRENGTH_12MA);
	gpio_set_drive_strength(SPI_SCK,  GPIO_DRIVE_STRENGTH_12MA);

	spi_enabled = 1;
}

static void disable_pin(uint pin) {
	gpio_init(pin);            /* Set pin to SIO input */
	gpio_set_pulls(pin, 0, 0); /* Disable all pulls */
}

static void disable_spi() {
	for (uint8_t i=0; i<NUM_CS_AVAILABLE; i++)
		disable_pin(SPI_CS_0 + i);
	disable_pin(SPI_MISO);
	disable_pin(SPI_MOSI);
	disable_pin(SPI_SCK);

	/* Disable SPI peripheral */
	spi_deinit(SPI_IF);

	spi_enabled = 0;
}


static inline void cs_select(uint cs_pin) {
	asm volatile("nop \n nop \n nop"); /* FIXME */
	gpio_put(cs_pin, 0);
	asm volatile("nop \n nop \n nop"); /* FIXME */
}

static inline void cs_deselect(uint cs_pin) {
	asm volatile("nop \n nop \n nop"); /* FIXME */
	gpio_put(cs_pin, 1);
	asm volatile("nop \n nop \n nop"); /* FIXME */
}

static void wait_for_read(void) {
	do
	    tud_task();
	while (!tud_cdc_n_available(CDC_ITF));
}

static inline void readbytes_blocking(void *b, uint32_t len) {
	while (len) {
		wait_for_read();
		uint32_t r = tud_cdc_n_read(CDC_ITF, b, len);
		b += r;
		len -= r;
	}
}

static inline uint8_t readbyte_blocking(void) {
	wait_for_read();
	uint8_t b;
	tud_cdc_n_read(CDC_ITF, &b, 1);
	return b;
}

static void wait_for_write(void) {
	do {
		tud_task();
	} while (!tud_cdc_n_write_available(CDC_ITF));
}

static inline void sendbytes_blocking(const void *b, uint32_t len) {
	while (len) {
		wait_for_write();
		uint32_t w = tud_cdc_n_write(CDC_ITF, b, len);
		b += w;
		len -= w;
	}
}

static inline void sendbyte_blocking(uint8_t b) {
	wait_for_write();
	tud_cdc_n_write(CDC_ITF, &b, 1);
}

void s_cmd_s_bustype() {
	/* If SPI is among the requested bus types we succeed,
	 * fail otherwise */
	if ((uint8_t) readbyte_blocking() & (1 << 3))
		sendbyte_blocking(S_ACK);
	else
		sendbyte_blocking(S_NAK);
}

void s_cmd_o_spiop() {
	static uint8_t buf[4096];
	uint32_t wlen = 0;
	uint32_t rlen = 0;
	readbytes_blocking(&wlen, 3);
	readbytes_blocking(&rlen, 3);

	cs_select(cs_pin);

	while (wlen) {
		uint32_t cur = MIN(wlen, sizeof buf);
		readbytes_blocking(buf, cur);
		spi_write_blocking(SPI_IF, buf, cur);
		wlen -= cur;
	}

	sendbyte_blocking(S_ACK);

	while (rlen) {
		uint32_t cur = MIN(rlen, sizeof buf);
		spi_read_blocking(SPI_IF, 0, buf, cur);
		sendbytes_blocking(buf, cur);
		rlen -= cur;
	}

	cs_deselect(cs_pin);
}

void s_cmd_s_spi_freq() {
	uint32_t want_baud;
	readbytes_blocking(&want_baud, 4);
	if (want_baud) {
		/* Set frequency */
		baud = spi_set_baudrate(SPI_IF, want_baud);
		/* Send back actual value */
		sendbyte_blocking(S_ACK);
		sendbytes_blocking(&baud, 4);
	} else {
		/* 0 Hz is reserved */
		sendbyte_blocking(S_NAK);
	}
}

void s_cmd_s_pin_state() {
	if (readbyte_blocking())
		enable_spi();
	else
		disable_spi();
	sendbyte_blocking(S_ACK);
}

void s_cmd_s_spi_cs() {
	uint8_t cs = readbyte_blocking();
	if (cs >= NUM_CS_AVAILABLE)
		sendbyte_blocking(S_NAK);
	return;

	cs += SPI_CS_0;
	if (spi_enabled) {
		if (cs_pin != cs) {
			pullup_cs(cs_pin);
			use_cs(cs);
		}
	}
	cs_pin = cs;
	sendbyte_blocking(S_ACK);
}


static void command_loop() {
	while (1) {
		uint8_t cmd = readbyte_blocking();
#ifdef PICO_DEFAULT_LED_PIN
		gpio_put(PICO_DEFAULT_LED_PIN, 1);
#endif
		switch (cmd) {
		case S_CMD_NOP:
			sendbyte_blocking(S_ACK);
			break;
		case S_CMD_Q_IFACE:
			sendbyte_blocking(S_ACK);
			sendbyte_blocking(0x01);
			sendbyte_blocking(0x00);
			break;
		case S_CMD_Q_CMDMAP:
			sendbyte_blocking(S_ACK);
			sendbytes_blocking((uint8_t *)cmdmap, sizeof(cmdmap));
			break;
		case S_CMD_Q_PGMNAME:
			sendbyte_blocking(S_ACK);
			sendbytes_blocking(progname, sizeof(progname));
			break;
		case S_CMD_Q_SERBUF:
			sendbyte_blocking(S_ACK);
			sendbyte_blocking(0xFF);
			sendbyte_blocking(0xFF);
			break;
		case S_CMD_Q_BUSTYPE:
			sendbyte_blocking(S_ACK);
			sendbyte_blocking((1 << 3)); /* SPI */
			break;
		case S_CMD_SYNCNOP:
			sendbyte_blocking(S_NAK);
			sendbyte_blocking(S_ACK);
			break;
		case S_CMD_S_BUSTYPE:
			s_cmd_s_bustype();
			break;
		case S_CMD_O_SPIOP:
			s_cmd_o_spiop();
			break;
		case S_CMD_S_SPI_FREQ:
			s_cmd_s_spi_freq();
			break;
		case S_CMD_S_PIN_STATE:
			s_cmd_s_pin_state();
			break;
		case S_CMD_S_SPI_CS:
			s_cmd_s_spi_cs();
			break;
		default:
			sendbyte_blocking(S_NAK);
		}

		tud_cdc_n_write_flush(CDC_ITF);

#ifdef PICO_DEFAULT_LED_PIN
		gpio_put(PICO_DEFAULT_LED_PIN, 0);
#endif
	}
}

int main() {
	/* Metadata for picotool */
	bi_decl(bi_program_description(DESCRIPTION));
	bi_decl(bi_program_url(WEBSITE));
#ifdef PICO_DEFAULT_LED_PIN
	bi_decl(bi_1pin_with_name(PICO_DEFAULT_LED_PIN, "Activity LED"));
#endif
	bi_decl(bi_1pin_with_name(SPI_MISO, "MISO"));
	bi_decl(bi_1pin_with_name(SPI_MOSI, "MOSI"));
	bi_decl(bi_1pin_with_name(SPI_SCK, "SCK"));
	bi_decl(bi_1pin_with_name(SPI_CS_0,   "CS_0 (default)"));
	bi_decl(bi_1pin_with_name(SPI_CS_0+1, "CS_1"));
	bi_decl(bi_1pin_with_name(SPI_CS_0+2, "CS_2"));
	bi_decl(bi_1pin_with_name(SPI_CS_0+3, "CS_3"));

	/* Setup USB */
	tusb_init();
	/* Setup PL022 SPI */
	enable_spi();

	command_loop();
}

