/* eslint-disable operator-linebreak */
// IST8310 Compass Extension for KittenBlock (kblock.kittenbot.cc)
// Compatible with Future Board AI (FutureLite ESP32-S3-FN8)
// IST8310 3-axis magnetometer on I2C(1): SCL=GPIO1, SDA=GPIO2
// Tilt-compensated heading using onboard accelerometer

const _Scratch = (typeof Scratch !== 'undefined') ? Scratch : {};
const _BT = _Scratch.BlockType || {};
const _AT = _Scratch.ArgumentType || {};

const ArgumentType = {
    ANGLE:   _AT.ANGLE   || 'angle',
    BOOLEAN: _AT.BOOLEAN || 'Boolean',
    COLOR:   _AT.COLOR   || 'color',
    IMAGE:   _AT.IMAGE   || 'image',
    MATRIX:  _AT.MATRIX  || 'matrix',
    NOTE:    _AT.NOTE    || 'note',
    NUMBER:  _AT.NUMBER  || 'Number',
    STRING:  _AT.STRING  || 'String',
};

const BlockType = {
    BOOLEAN:     _BT.BOOLEAN     || 'Boolean',
    COMMAND:     _BT.COMMAND     || 'command',
    CONDITIONAL: _BT.CONDITIONAL || 'conditional',
    DIVLABEL:    _BT.DIVLABEL    || 'label',
    EVENT:       _BT.EVENT       || 'event',
    HAT:         _BT.HAT         || 'hat',
    LOOP:        _BT.LOOP        || 'loop',
    REPORTER:    _BT.REPORTER    || 'reporter',
};

const formatMessage = _Scratch.formatMessage || function(obj) {
    if (typeof obj === 'string') return obj;
    return obj.default || obj.id || '';
};
const log = (_Scratch.log || console.log).bind(console);

// ─── Compass SVG icon (base64 encoded inline SVG) ──────────────────────────
const menuIconURI = "data:image/svg+xml;base64," + btoa(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle cx="50" cy="50" r="48" fill="#1a237e" stroke="#5c6bc0" stroke-width="2"/>
  <circle cx="50" cy="50" r="40" fill="none" stroke="#3949ab" stroke-width="1"/>
  <text x="50" y="14" text-anchor="middle" fill="#ef5350" font-size="12" font-weight="bold" font-family="Arial">N</text>
  <text x="50" y="93" text-anchor="middle" fill="#90caf9" font-size="12" font-family="Arial">S</text>
  <text x="90" y="55" text-anchor="middle" fill="#90caf9" font-size="12" font-family="Arial">E</text>
  <text x="10" y="55" text-anchor="middle" fill="#90caf9" font-size="12" font-family="Arial">W</text>
  <polygon points="50,18 46,50 54,50" fill="#ef5350"/>
  <polygon points="50,82 46,50 54,50" fill="#e0e0e0"/>
  <circle cx="50" cy="50" r="4" fill="#ffd700"/>
  <text x="50" y="75" text-anchor="middle" fill="#80cbc4" font-size="8" font-family="Arial">IST8310</text>
</svg>`);

const blockIconURI = menuIconURI;

// ─── Serial Communication Helper ──────────────────────────────────────────
// Communicates with the Future Board via USB serial (WebSerial or KittenBlock's robot serial)

class IST8310CompassExtension {
    constructor (runtime) {
        this.runtime = runtime;
        this._connected = false;
        this._port = null;
        this._writer = null;
        this._reader = null;
        this._readBuffer = '';
        this._lastData = {
            heading: 0,
            dir: 'N',
            mx: 0, my: 0, mz: 0,
            pitch: 0, roll: 0,
            field: 0
        };
        this._updateInterval = null;
        this._useRobotSerial = false;

        // Try to use KittenBlock's built-in robot serial
        if (runtime && runtime.ioDevices && runtime.ioDevices.kb_robot) {
            this._useRobotSerial = true;
            log('[IST8310] Using KittenBlock kb_robot serial');
        }

        if (runtime && typeof runtime.registerPeripheralExtension === 'function') {
            try { runtime.registerPeripheralExtension('IST8310Compass', this); } catch(e) {}
        }
    }

    // ─── WebSerial connection ──────────────────────────────────────────────

    async _connectWebSerial() {
        if (!navigator.serial) {
            throw new Error('WebSerial not supported. Please use Chrome/Edge browser.');
        }
        try {
            this._port = await navigator.serial.requestPort();
            await this._port.open({ baudRate: 115200 });
            this._writer = this._port.writable.getWriter();
            this._connected = true;
            log('[IST8310] WebSerial connected');
            // Start reading
            this._startReading();
            // Start polling
            this._startPolling();
            return true;
        } catch (e) {
            log('[IST8310] WebSerial connect error:', e.message);
            throw e;
        }
    }

    _startReading() {
        if (!this._port || !this._port.readable) return;
        const decoder = new TextDecoder();
        const reader = this._port.readable.getReader();
        this._reader = reader;

        const readLoop = async () => {
            try {
                while (this._connected) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    const text = decoder.decode(value);
                    this._readBuffer += text;
                    // Process complete lines
                    const lines = this._readBuffer.split('\n');
                    this._readBuffer = lines.pop(); // Keep incomplete line
                    for (const line of lines) {
                        this._processLine(line.trim());
                    }
                }
            } catch (e) {
                if (this._connected) log('[IST8310] Read error:', e.message);
            }
        };
        readLoop();
    }

    _processLine(line) {
        if (!line) return;
        try {
            const data = JSON.parse(line);
            if (data.heading !== undefined) {
                this._lastData = Object.assign(this._lastData, data);
            }
        } catch (e) {
            // Not JSON, ignore
        }
    }

    async _sendCommand(cmd) {
        if (this._useRobotSerial && this.runtime.ioDevices.kb_robot) {
            const robot = this.runtime.ioDevices.kb_robot;
            try {
                const json = JSON.stringify(cmd) + '\n';
                if (typeof robot.send === 'function') {
                    robot.send(json);
                } else if (typeof robot.write === 'function') {
                    robot.write(json);
                }
                return true;
            } catch (e) {
                log('[IST8310] kb_robot send error:', e.message);
            }
        }

        if (this._connected && this._writer) {
            const encoder = new TextEncoder();
            const data = encoder.encode(JSON.stringify(cmd) + '\n');
            await this._writer.write(data);
            return true;
        }
        return false;
    }

    async _queryAndWait(action, timeout = 2000) {
        return new Promise(async (resolve) => {
            const prevData = JSON.stringify(this._lastData);
            await this._sendCommand({ action });
            
            // Wait for response (data change or timeout)
            const start = Date.now();
            const check = () => {
                if (JSON.stringify(this._lastData) !== prevData) {
                    resolve(this._lastData);
                } else if (Date.now() - start > timeout) {
                    resolve(this._lastData); // Return last known data on timeout
                } else {
                    setTimeout(check, 50);
                }
            };
            setTimeout(check, 50);
        });
    }

    _startPolling() {
        if (this._updateInterval) clearInterval(this._updateInterval);
        this._updateInterval = setInterval(async () => {
            if (this._connected || this._useRobotSerial) {
                this._sendCommand({ action: 'getAll' });
            }
        }, 300); // Poll every 300ms
    }

    _stopPolling() {
        if (this._updateInterval) {
            clearInterval(this._updateInterval);
            this._updateInterval = null;
        }
    }

    async _disconnect() {
        this._stopPolling();
        this._connected = false;
        if (this._reader) {
            try { await this._reader.cancel(); } catch(e) {}
            this._reader = null;
        }
        if (this._writer) {
            try { await this._writer.close(); } catch(e) {}
            this._writer = null;
        }
        if (this._port) {
            try { await this._port.close(); } catch(e) {}
            this._port = null;
        }
    }

    // ─── KittenBlock Extension Info ────────────────────────────────────────

    getInfo() {
        return {
            id: 'IST8310Compass',
            name: 'IST8310 羅盤',
            color1: '#1a237e',
            color2: '#283593',
            color3: '#3949ab',
            menuIconURI: menuIconURI,
            blockIconURI: blockIconURI,
            blocks: [
                // ── 連接/設置 ──
                {
                    func: 'noop',
                    blockType: BlockType.DIVLABEL,
                    text: '🔌 連接設置'
                },
                {
                    opcode: 'block_connect',
                    blockType: BlockType.COMMAND,
                    text: '連接 IST8310 羅盤 (USB串口)',
                    func: 'block_connect',
                    sepafter: 12
                },
                {
                    opcode: 'block_connect_robot',
                    blockType: BlockType.COMMAND,
                    text: '連接 IST8310 羅盤 (KittenBlock設備)',
                    func: 'block_connect_robot',
                    sepafter: 24
                },
                {
                    opcode: 'block_is_connected',
                    blockType: BlockType.BOOLEAN,
                    text: '羅盤已連接?',
                    func: 'block_is_connected'
                },
                {
                    opcode: 'block_disconnect',
                    blockType: BlockType.COMMAND,
                    text: '斷開連接',
                    func: 'block_disconnect',
                    sepafter: 36
                },

                // ── 羅盤航向 ──
                {
                    func: 'noop',
                    blockType: BlockType.DIVLABEL,
                    text: '🧭 羅盤航向'
                },
                {
                    opcode: 'block_update',
                    blockType: BlockType.COMMAND,
                    text: '更新羅盤數據',
                    func: 'block_update',
                    sepafter: 12
                },
                {
                    opcode: 'block_heading',
                    blockType: BlockType.REPORTER,
                    text: '航向角度 (°)',
                    func: 'block_heading'
                },
                {
                    opcode: 'block_direction',
                    blockType: BlockType.REPORTER,
                    text: '羅盤方向',
                    func: 'block_direction'
                },
                {
                    opcode: 'block_facing',
                    blockType: BlockType.BOOLEAN,
                    text: '正在朝向 [DIR] ?',
                    arguments: {
                        DIR: {
                            type: ArgumentType.STRING,
                            menu: 'directions',
                            defaultValue: 'N'
                        }
                    },
                    func: 'block_facing',
                    sepafter: 12
                },
                {
                    opcode: 'block_heading_between',
                    blockType: BlockType.BOOLEAN,
                    text: '航向在 [MIN] ° 和 [MAX] ° 之間?',
                    arguments: {
                        MIN: {
                            type: ArgumentType.NUMBER,
                            defaultValue: 0
                        },
                        MAX: {
                            type: ArgumentType.NUMBER,
                            defaultValue: 45
                        }
                    },
                    func: 'block_heading_between',
                    sepafter: 36
                },

                // ── 磁場數據 ──
                {
                    func: 'noop',
                    blockType: BlockType.DIVLABEL,
                    text: '🔮 磁場數據 (µT)'
                },
                {
                    opcode: 'block_mag_x',
                    blockType: BlockType.REPORTER,
                    text: '磁場 X (µT)',
                    func: 'block_mag_x'
                },
                {
                    opcode: 'block_mag_y',
                    blockType: BlockType.REPORTER,
                    text: '磁場 Y (µT)',
                    func: 'block_mag_y'
                },
                {
                    opcode: 'block_mag_z',
                    blockType: BlockType.REPORTER,
                    text: '磁場 Z (µT)',
                    func: 'block_mag_z'
                },
                {
                    opcode: 'block_field_strength',
                    blockType: BlockType.REPORTER,
                    text: '磁場強度 (µT)',
                    func: 'block_field_strength',
                    sepafter: 36
                },

                // ── 姿態角度 ──
                {
                    func: 'noop',
                    blockType: BlockType.DIVLABEL,
                    text: '📐 姿態角度'
                },
                {
                    opcode: 'block_pitch',
                    blockType: BlockType.REPORTER,
                    text: '俯仰角 Pitch (°)',
                    func: 'block_pitch'
                },
                {
                    opcode: 'block_roll',
                    blockType: BlockType.REPORTER,
                    text: '橫滾角 Roll (°)',
                    func: 'block_roll',
                    sepafter: 36
                },

                // ── 校準 ──
                {
                    func: 'noop',
                    blockType: BlockType.DIVLABEL,
                    text: '⚙️ 校準'
                },
                {
                    opcode: 'block_start_calibration',
                    blockType: BlockType.COMMAND,
                    text: '開始磁場校準 (按未來板 A 鍵)',
                    func: 'block_start_calibration'
                },
                {
                    opcode: 'block_stop_calibration',
                    blockType: BlockType.COMMAND,
                    text: '完成校準並儲存 (按未來板 B 鍵)',
                    func: 'block_stop_calibration'
                },
            ],

            menus: {
                directions: {
                    acceptReporters: true,
                    items: [
                        { text: '北 (N)',  value: 'N'  },
                        { text: '東北 (NE)', value: 'NE' },
                        { text: '東 (E)',  value: 'E'  },
                        { text: '東南 (SE)', value: 'SE' },
                        { text: '南 (S)',  value: 'S'  },
                        { text: '西南 (SW)', value: 'SW' },
                        { text: '西 (W)',  value: 'W'  },
                        { text: '西北 (NW)', value: 'NW' }
                    ]
                }
            }
        };
    }

    // ─── Block Implementations ─────────────────────────────────────────────

    noop() {}

    async block_connect(args, util) {
        try {
            await this._connectWebSerial();
            // Send ping to verify connection
            await this._sendCommand({ action: 'ping' });
            await new Promise(r => setTimeout(r, 500));
            this._startPolling();
            log('[IST8310] Connected via WebSerial');
        } catch (e) {
            log('[IST8310] Connect failed:', e.message);
            alert('連接失敗: ' + e.message + '\n請確保:\n1. 使用 Chrome 或 Edge 瀏覽器\n2. 未來板已透過 USB 連接\n3. 未來板正在運行 IST8310 程式');
        }
    }

    async block_connect_robot(args, util) {
        // Use KittenBlock's built-in device connection
        this._useRobotSerial = true;
        this._connected = false; // Use robot serial instead
        
        if (this.runtime && this.runtime.ioDevices && this.runtime.ioDevices.kb_robot) {
            const robot = this.runtime.ioDevices.kb_robot;
            // Set up message listener
            if (typeof robot.on === 'function') {
                robot.on('message', (data) => {
                    const text = typeof data === 'string' ? data : data.toString();
                    text.split('\n').forEach(line => this._processLine(line.trim()));
                });
            } else if (typeof robot.addListener === 'function') {
                robot.addListener('message', (data) => {
                    const text = typeof data === 'string' ? data : data.toString();
                    text.split('\n').forEach(line => this._processLine(line.trim()));
                });
            }
            
            await this._sendCommand({ action: 'ping' });
            this._startPolling();
            log('[IST8310] Using KittenBlock robot serial');
        } else {
            log('[IST8310] kb_robot not available, falling back to WebSerial');
            return this.block_connect(args, util);
        }
    }

    block_disconnect(args, util) {
        this._disconnect();
        this._useRobotSerial = false;
        log('[IST8310] Disconnected');
    }

    block_is_connected(args, util) {
        return this._connected || this._useRobotSerial;
    }

    async block_update(args, util) {
        await this._sendCommand({ action: 'getAll' });
        await new Promise(r => setTimeout(r, 350));
    }

    block_heading(args, util) {
        return Math.round(this._lastData.heading * 10) / 10;
    }

    block_direction(args, util) {
        const dirMap = {
            'N': '北', 'NE': '東北', 'E': '東', 'SE': '東南',
            'S': '南', 'SW': '西南', 'W': '西', 'NW': '西北'
        };
        const dir = this._lastData.dir || 'N';
        return `${dir} (${dirMap[dir] || dir})`;
    }

    block_facing(args, util) {
        return this._lastData.dir === args.DIR;
    }

    block_heading_between(args, util) {
        const h = this._lastData.heading;
        const min = parseFloat(args.MIN);
        const max = parseFloat(args.MAX);
        if (min <= max) {
            return h >= min && h <= max;
        } else {
            // Wrap-around (e.g., 350° to 10°)
            return h >= min || h <= max;
        }
    }

    block_mag_x(args, util) {
        return Math.round(this._lastData.mx * 100) / 100;
    }

    block_mag_y(args, util) {
        return Math.round(this._lastData.my * 100) / 100;
    }

    block_mag_z(args, util) {
        return Math.round(this._lastData.mz * 100) / 100;
    }

    block_field_strength(args, util) {
        const { mx, my, mz } = this._lastData;
        return Math.round(Math.sqrt(mx*mx + my*my + mz*mz) * 100) / 100;
    }

    block_pitch(args, util) {
        return Math.round(this._lastData.pitch * 10) / 10;
    }

    block_roll(args, util) {
        return Math.round(this._lastData.roll * 10) / 10;
    }

    async block_start_calibration(args, util) {
        await this._sendCommand({ action: 'startCalibration' });
        log('[IST8310] Calibration started');
    }

    async block_stop_calibration(args, util) {
        await this._sendCommand({ action: 'stopCalibration' });
        await new Promise(r => setTimeout(r, 300));
        log('[IST8310] Calibration stopped');
    }
}

module.exports = IST8310CompassExtension;
