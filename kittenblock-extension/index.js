/**
 * IST8310 Compass Extension for KittenBlock (Future Board AI)
 * 
 * Plugin for kblock.kittenblock.cc
 * Provides blocks for:
 *   - Reading IST8310 magnetometer (X, Y, Z)
 *   - Reading tilt-compensated heading (compass angle)
 *   - Reading pitch and roll
 *   - Calibration control
 * 
 * Protocol: JSON over USB serial to Future Board AI (ESP32-S3)
 * Main.py on the board handles the serial commands.
 */

(function (Scratch) {
    'use strict';

    // ─────────────────────────────────────────
    // Extension Metadata
    // ─────────────────────────────────────────
    const ExtensionInfo = {
        id: 'ist8310compass',
        name: 'IST8310 Compass',
        color1: '#1565C0',
        color2: '#0D47A1',
        color3: '#0D47A1',
        menuIconURI: 'data:image/svg+xml;base64,' + btoa(`
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">
  <circle cx="20" cy="20" r="18" fill="#1565C0" stroke="#42A5F5" stroke-width="2"/>
  <circle cx="20" cy="20" r="14" fill="none" stroke="#90CAF9" stroke-width="1"/>
  <text x="20" y="10" text-anchor="middle" fill="white" font-size="6" font-family="Arial">N</text>
  <text x="20" y="34" text-anchor="middle" fill="#aaa" font-size="6" font-family="Arial">S</text>
  <text x="32" y="22" text-anchor="middle" fill="#aaa" font-size="6" font-family="Arial">E</text>
  <text x="8" y="22" text-anchor="middle" fill="#aaa" font-size="6" font-family="Arial">W</text>
  <polygon points="20,8 22,22 20,21 18,22" fill="#EF5350"/>
  <polygon points="20,32 22,18 20,19 18,18" fill="white"/>
  <circle cx="20" cy="20" r="2.5" fill="#FFD740"/>
</svg>`),
        blockIconURI: 'data:image/svg+xml;base64,' + btoa(`
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">
  <circle cx="20" cy="20" r="18" fill="#1565C0"/>
  <polygon points="20,6 22,20 20,19 18,20" fill="#EF5350"/>
  <polygon points="20,34 22,20 20,21 18,20" fill="white"/>
  <circle cx="20" cy="20" r="3" fill="#FFD740"/>
</svg>`),
    };

    // ─────────────────────────────────────────
    // State variables
    // ─────────────────────────────────────────
    let _heading = 0;
    let _magX = 0, _magY = 0, _magZ = 0;
    let _pitch = 0, _roll = 0;
    let _direction = 'N';
    let _connected = false;
    let _lastUpdate = 0;
    let _updateInterval = null;

    // ─────────────────────────────────────────
    // Serial communication helper
    // ─────────────────────────────────────────
    function sendCommand(runtime, action, params) {
        return new Promise((resolve, reject) => {
            try {
                const cmd = JSON.stringify(Object.assign({ action }, params || {})) + '\n';
                
                // Use KittenBlock's serial/robot interface
                if (runtime.ioDevices && runtime.ioDevices.kb_robot) {
                    runtime.ioDevices.kb_robot.write(cmd);
                } else if (window._kblock_serial && window._kblock_serial.write) {
                    window._kblock_serial.write(cmd);
                } else if (runtime.peripheralExtensions) {
                    // Try Scratch peripheral system
                    const peripheral = runtime.peripheralExtensions['ist8310compass'];
                    if (peripheral && peripheral.write) {
                        peripheral.write(cmd);
                    }
                }
                resolve(true);
            } catch (e) {
                console.warn('[IST8310] sendCommand error:', e);
                resolve(false);
            }
        });
    }

    // ─────────────────────────────────────────
    // Parse incoming serial data line
    // ─────────────────────────────────────────
    function parseResponse(line) {
        try {
            const data = JSON.parse(line.trim());
            
            if (data.heading !== undefined) {
                _heading = parseFloat(data.heading) || 0;
                if (data.dir) _direction = data.dir;
            }
            if (data.mx !== undefined) {
                _magX = parseFloat(data.mx) || 0;
                _magY = parseFloat(data.my) || 0;
                _magZ = parseFloat(data.mz) || 0;
            }
            if (data.pitch !== undefined) {
                _pitch = parseFloat(data.pitch) || 0;
                _roll  = parseFloat(data.roll)  || 0;
            }
            if (data.status === 'ok') {
                _connected = true;
            }
            _lastUpdate = Date.now();
        } catch (e) {
            // Not JSON, ignore
        }
    }

    // ─────────────────────────────────────────
    // Extension Class
    // ─────────────────────────────────────────
    class IST8310CompassExtension {
        constructor(runtime) {
            this.runtime = runtime;
            this._runtime = runtime;
            this._serialBuf = '';

            // Listen for serial data from Future Board
            this._setupSerialListener();

            console.log('[IST8310] Compass extension loaded');
        }

        getInfo() {
            return {
                ...ExtensionInfo,
                blocks: [
                    // ── Section: Connection ──
                    {
                        blockType: Scratch.BlockType.LABEL,
                        text: '🔌 Connection',
                    },
                    {
                        opcode: 'ping',
                        blockType: Scratch.BlockType.COMMAND,
                        text: 'Connect IST8310 compass',
                        arguments: {},
                    },
                    {
                        opcode: 'isConnected',
                        blockType: Scratch.BlockType.BOOLEAN,
                        text: 'compass connected?',
                        arguments: {},
                    },

                    // ── Section: Compass Heading ──
                    '---',
                    {
                        blockType: Scratch.BlockType.LABEL,
                        text: '🧭 Compass',
                    },
                    {
                        opcode: 'getHeading',
                        blockType: Scratch.BlockType.REPORTER,
                        text: 'compass heading (°)',
                        arguments: {},
                    },
                    {
                        opcode: 'getDirection',
                        blockType: Scratch.BlockType.REPORTER,
                        text: 'compass direction',
                        arguments: {},
                    },
                    {
                        opcode: 'isHeadingBetween',
                        blockType: Scratch.BlockType.BOOLEAN,
                        text: 'heading between [MIN] and [MAX] °',
                        arguments: {
                            MIN: { type: Scratch.ArgumentType.NUMBER, defaultValue: 350 },
                            MAX: { type: Scratch.ArgumentType.NUMBER, defaultValue: 10  },
                        },
                    },
                    {
                        opcode: 'isFacingDirection',
                        blockType: Scratch.BlockType.BOOLEAN,
                        text: 'facing [DIR]?',
                        arguments: {
                            DIR: {
                                type: Scratch.ArgumentType.STRING,
                                menu: 'directionMenu',
                                defaultValue: 'N',
                            },
                        },
                    },

                    // ── Section: Magnetometer Raw ──
                    '---',
                    {
                        blockType: Scratch.BlockType.LABEL,
                        text: '📡 Magnetometer (µT)',
                    },
                    {
                        opcode: 'getMagX',
                        blockType: Scratch.BlockType.REPORTER,
                        text: 'magnetometer X (µT)',
                        arguments: {},
                    },
                    {
                        opcode: 'getMagY',
                        blockType: Scratch.BlockType.REPORTER,
                        text: 'magnetometer Y (µT)',
                        arguments: {},
                    },
                    {
                        opcode: 'getMagZ',
                        blockType: Scratch.BlockType.REPORTER,
                        text: 'magnetometer Z (µT)',
                        arguments: {},
                    },
                    {
                        opcode: 'getMagField',
                        blockType: Scratch.BlockType.REPORTER,
                        text: 'magnetic field strength (µT)',
                        arguments: {},
                    },

                    // ── Section: Tilt ──
                    '---',
                    {
                        blockType: Scratch.BlockType.LABEL,
                        text: '📐 Tilt Angles',
                    },
                    {
                        opcode: 'getPitch',
                        blockType: Scratch.BlockType.REPORTER,
                        text: 'pitch angle (°)',
                        arguments: {},
                    },
                    {
                        opcode: 'getRoll',
                        blockType: Scratch.BlockType.REPORTER,
                        text: 'roll angle (°)',
                        arguments: {},
                    },

                    // ── Section: Calibration ──
                    '---',
                    {
                        blockType: Scratch.BlockType.LABEL,
                        text: '⚙️ Calibration',
                    },
                    {
                        opcode: 'startCalibration',
                        blockType: Scratch.BlockType.COMMAND,
                        text: 'start calibration (rotate device)',
                        arguments: {},
                    },
                    {
                        opcode: 'stopCalibration',
                        blockType: Scratch.BlockType.COMMAND,
                        text: 'stop calibration and save',
                        arguments: {},
                    },

                    // ── Section: Update ──
                    '---',
                    {
                        opcode: 'updateSensor',
                        blockType: Scratch.BlockType.COMMAND,
                        text: 'update compass data',
                        arguments: {},
                    },
                ],
                menus: {
                    directionMenu: {
                        acceptReporters: false,
                        items: ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'],
                    },
                },
            };
        }

        // ─────────────────────────────────────
        // Block implementations
        // ─────────────────────────────────────

        async ping(args) {
            await sendCommand(this.runtime, 'ping');
            return new Promise(resolve => setTimeout(resolve, 500));
        }

        isConnected(args) {
            // Connected if we got data in last 3 seconds
            return _connected && (Date.now() - _lastUpdate < 3000);
        }

        async getHeading(args) {
            await sendCommand(this.runtime, 'getHeading');
            return Math.round(_heading * 10) / 10;
        }

        getDirection(args) {
            return _direction;
        }

        isHeadingBetween(args) {
            const min = parseFloat(args.MIN);
            const max = parseFloat(args.MAX);
            // Handle wrap-around (e.g., 350-10)
            if (min > max) {
                return _heading >= min || _heading <= max;
            }
            return _heading >= min && _heading <= max;
        }

        isFacingDirection(args) {
            const dirMap = { N:0, NE:45, E:90, SE:135, S:180, SW:225, W:270, NW:315 };
            const target = dirMap[args.DIR] || 0;
            const diff = Math.abs((_heading - target + 540) % 360 - 180);
            return diff <= 22.5;
        }

        async getMagX(args) {
            await sendCommand(this.runtime, 'getMag');
            return Math.round(_magX * 10) / 10;
        }

        async getMagY(args) {
            await sendCommand(this.runtime, 'getMag');
            return Math.round(_magY * 10) / 10;
        }

        async getMagZ(args) {
            await sendCommand(this.runtime, 'getMag');
            return Math.round(_magZ * 10) / 10;
        }

        getMagField(args) {
            return Math.round(Math.sqrt(_magX*_magX + _magY*_magY + _magZ*_magZ) * 10) / 10;
        }

        async getPitch(args) {
            await sendCommand(this.runtime, 'getPitchRoll');
            return Math.round(_pitch * 10) / 10;
        }

        async getRoll(args) {
            await sendCommand(this.runtime, 'getPitchRoll');
            return Math.round(_roll * 10) / 10;
        }

        async startCalibration(args) {
            await sendCommand(this.runtime, 'startCalibration');
        }

        async stopCalibration(args) {
            await sendCommand(this.runtime, 'stopCalibration');
            return new Promise(resolve => setTimeout(resolve, 500));
        }

        async updateSensor(args) {
            await sendCommand(this.runtime, 'getHeading');
            await sendCommand(this.runtime, 'getMag');
            await sendCommand(this.runtime, 'getPitchRoll');
            return new Promise(resolve => setTimeout(resolve, 100));
        }

        // ─────────────────────────────────────
        // Serial listener setup
        // ─────────────────────────────────────
        _setupSerialListener() {
            // Listen on KittenBlock's serial event system
            const tryListen = () => {
                if (this.runtime.ioDevices && this.runtime.ioDevices.kb_robot) {
                    const robot = this.runtime.ioDevices.kb_robot;
                    if (robot.on) {
                        robot.on('data', (data) => {
                            this._serialBuf += (typeof data === 'string') ? data : new TextDecoder().decode(data);
                            let lines = this._serialBuf.split('\n');
                            this._serialBuf = lines.pop();
                            lines.forEach(line => parseResponse(line));
                        });
                        console.log('[IST8310] Serial listener attached to kb_robot');
                        return true;
                    }
                }
                return false;
            };

            if (!tryListen()) {
                // Retry after 2 seconds
                setTimeout(() => {
                    tryListen();
                }, 2000);
            }

            // Also listen on global serial if available
            if (window._kblock_serial_emitter) {
                window._kblock_serial_emitter.on('data', (data) => {
                    this._serialBuf += data;
                    let lines = this._serialBuf.split('\n');
                    this._serialBuf = lines.pop();
                    lines.forEach(line => parseResponse(line));
                });
            }
        }
    }

    // ─────────────────────────────────────────
    // Register extension with Scratch/KittenBlock
    // ─────────────────────────────────────────
    Scratch.extensions.register(new IST8310CompassExtension(Scratch.vm.runtime));

})(window.Scratch || window.ScratchExtensions || (() => {
    // Fallback for direct loading
    return {
        extensions: {
            register: (ext) => console.log('[IST8310] Extension registered:', ext)
        },
        BlockType: { COMMAND: 'command', REPORTER: 'reporter', BOOLEAN: 'Boolean', LABEL: 'label' },
        ArgumentType: { STRING: 'string', NUMBER: 'number' },
        vm: { runtime: {} }
    };
})());
