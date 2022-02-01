/*
 * AmpliPi Home Audio
 * Copyright (C) 2021 MicroNova LLC
 *
 * Port usage and functions for GPIO
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

#ifndef PORTS_H_
#define PORTS_H_

#include <stdbool.h>
#include <stdint.h>

typedef struct {
  char    port;  // Valid ports in our case are A,B,C,D,F
  uint8_t pin : 4;
} Pin;

void writePin(Pin pp, bool set);
bool readPin(Pin pp);

typedef struct {
  uint8_t dev;
  uint8_t reg;
} I2CReg;

uint8_t  readI2C2(I2CReg r);
uint32_t writeI2C2(I2CReg r, uint8_t data);

#endif /* PORTS_H_ */
