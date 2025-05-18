"""
Nombre del alumno: Eduard Peñas Balart
Descripción general:
Este fichero contiene funciones para el manejo y procesamiento de señales WAVE en formato PCM lineal.
Permite convertir señales estéreo a mono, reconstruir señales estéreo a partir de señales mono, codificar señales estéreo como mono de 32 bits usando semisuma y semidiferencia, y descodificarlas de nuevo.

Funciones incluidas:
- leer_cabecera_wave
- escribir_cabecera_wave
- procesar_muestra
- estereo2mono
- mono2stereo
- codEstereo
- decEstereo
"""

import struct

def leer_cabecera_wave(f):
    """
    Lee y desempaqueta la cabecera de un archivo WAVE abierto en modo binario.
    Comprueba que el formato es RIFF/WAVE y PCM con 16 bits.

    Parametros:
    f -- archivo abierto en modo 'rb'

    Retorna:
    Un diccionario con los campos clave de la cabecera.
    """
    riff, size, wave = struct.unpack('<4sI4s', f.read(12))
    if riff != b'RIFF' or wave != b'WAVE':
        raise ValueError('Formato RIFF/WAVE no válido')

    fmt_id, fmt_size = struct.unpack('<4sI', f.read(8))
    if fmt_id != b'fmt ' or fmt_size != 16:
        raise ValueError('Subchunk fmt no válido o no PCM')

    fmt_data = struct.unpack('<HHIIHH', f.read(16))
    audio_format, num_channels, sample_rate, byte_rate, block_align, bits_per_sample = fmt_data

    data_id, data_size = struct.unpack('<4sI', f.read(8))
    if data_id != b'data':
        raise ValueError('Subchunk data no encontrado')

    return {
        'num_channels': num_channels,
        'sample_rate': sample_rate,
        'byte_rate': byte_rate,
        'block_align': block_align,
        'bits_per_sample': bits_per_sample,
        'data_size': data_size
    }

def escribir_cabecera_wave(f, num_channels, sample_rate, bits_per_sample, data_size):
    """
    Escribe una cabecera WAVE válida en un archivo en modo 'wb'.

    Parametros:
    f -- archivo abierto en modo 'wb'
    num_channels -- número de canales (1 = mono, 2 = estéreo)
    sample_rate -- frecuencia de muestreo en Hz
    bits_per_sample -- número de bits por muestra (16 o 32)
    data_size -- tamaño total de los datos de audio (en bytes)
    """
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    fmt_chunk_size = 16
    total_size = 4 + (8 + fmt_chunk_size) + (8 + data_size)

    f.write(struct.pack('<4sI4s', b'RIFF', total_size, b'WAVE'))
    f.write(struct.pack('<4sI', b'fmt ', fmt_chunk_size))
    f.write(struct.pack('<HHIIHH', 1, num_channels, sample_rate, byte_rate, block_align, bits_per_sample))
    f.write(struct.pack('<4sI', b'data', data_size))

def procesar_muestra(m, tam, canal):
    """
    Procesa una muestra estéreo binaria y devuelve una muestra mono según el canal especificado.

    Parametros:
    m -- muestra binaria de 2 canales
    tam -- tamaño en bytes de cada canal (normalmente 2)
    canal -- modo de conversión: 0 = izquierdo, 1 = derecho, 2 = semisuma, 3 = semidiferencia

    Retorna:
    Muestra binaria mono de un solo canal.
    """
    L = int.from_bytes(m[:tam], 'little', signed=True)
    R = int.from_bytes(m[tam:tam*2], 'little', signed=True)

    if canal == 0:
        res = L
    elif canal == 1:
        res = R
    elif canal == 2:
        res = (L + R) // 2
    elif canal == 3:
        res = (L - R) // 2
    else:
        raise ValueError('Canal inválido')

    return res.to_bytes(tam, 'little', signed=True)

def estereo2mono(ficEste, ficMono, canal=2):
    """
    Convierte un archivo estéreo WAVE de 16 bits a mono según el canal indicado.

    Parametros:
    ficEste -- ruta del archivo de entrada estéreo
    ficMono -- ruta del archivo de salida mono
        channel  -- modo de conversión:
                0 = solo canal izquierdo,
                1 = solo canal derecho,
                2 = promedio (semisuma),
                3 = semidiferencia (izq - der) / 2
    """
    with open(ficEste, 'rb') as f_in:
        cab = leer_cabecera_wave(f_in)
        if cab['num_channels'] != 2:
            raise ValueError('El archivo no es estéreo')
        datos = f_in.read(cab['data_size'])

    tam = cab['bits_per_sample'] // 8
    muestras = [datos[i:i+2*tam] for i in range(0, len(datos), 2*tam)]
    datos_mono = b''.join([procesar_muestra(m, tam, canal) for m in muestras])

    with open(ficMono, 'wb') as f_out:
        escribir_cabecera_wave(f_out, 1, cab['sample_rate'], cab['bits_per_sample'], len(datos_mono))
        f_out.write(datos_mono)

def mono2stereo(ficIzq, ficDer, ficEste):
    """
    Reconstruye un archivo estéreo a partir de dos archivos mono (izquierdo y derecho).

    Parametros:
    ficIzq -- archivo mono con el canal izquierdo
    ficDer -- archivo mono con el canal derecho
    ficEste -- archivo de salida estéreo reconstruido
    """
    with open(ficIzq, 'rb') as f_izq, open(ficDer, 'rb') as f_der:
        cab_izq = leer_cabecera_wave(f_izq)
        cab_der = leer_cabecera_wave(f_der)

        if cab_izq['num_channels'] != 1 or cab_der['num_channels'] != 1:
            raise ValueError('Ambos ficheros deben ser monofónicos')
        if cab_izq['sample_rate'] != cab_der['sample_rate']:
            raise ValueError('Las frecuencias de muestreo no coinciden')
        if cab_izq['bits_per_sample'] != cab_der['bits_per_sample']:
            raise ValueError('Los bits por muestra no coinciden')
        if cab_izq['data_size'] != cab_der['data_size']:
            raise ValueError('Las longitudes de los datos no coinciden')

        datos_izq = f_izq.read(cab_izq['data_size'])
        datos_der = f_der.read(cab_der['data_size'])

    tam = cab_izq['bits_per_sample'] // 8
    datos_stereo = b''.join([datos_izq[i:i+tam] + datos_der[i:i+tam] for i in range(0, len(datos_izq), tam)])

    with open(ficEste, 'wb') as f_out:
        escribir_cabecera_wave(f_out, 2, cab_izq['sample_rate'], cab_izq['bits_per_sample'], len(datos_stereo))
        f_out.write(datos_stereo)

def codEstereo(ficEste, ficCod):
    """
    Codifica una señal estéreo de 16 bits como una señal mono de 32 bits.
    La semisuma se guarda en los 16 bits altos y la semidiferencia en los 16 bits bajos.

    Parametros:
    ficEste -- archivo estéreo de entrada
    ficCod -- archivo mono de salida codificado
    """
    with open(ficEste, 'rb') as f_in:
        cab = leer_cabecera_wave(f_in)
        if cab['num_channels'] != 2 or cab['bits_per_sample'] != 16:
            raise ValueError('El fichero debe ser estéreo de 16 bits')
        datos = f_in.read(cab['data_size'])

    muestras = [struct.unpack('<hh', datos[i:i+4]) for i in range(0, len(datos), 4)]
    codificadas = [struct.pack('<I', (((L + R) // 2 & 0xFFFF) << 16) | ((L - R) // 2 & 0xFFFF)) for L, R in muestras]
    datos_cod = b''.join(codificadas)

    with open(ficCod, 'wb') as f_out:
        escribir_cabecera_wave(f_out, 1, cab['sample_rate'], 32, len(datos_cod))
        f_out.write(datos_cod)

def int16(x):
    """Convierte un entero de 16 bits sin signo a con signo."""
    return x if x < 0x8000 else x - 0x10000

def saturar16(x):
    """Recorta un entero para que esté dentro del rango de 16 bits con signo."""
    return max(-32768, min(32767, x))

def decEstereo(ficCod, ficEste):
    """
    Decodifica una señal mono de 32 bits en una señal estéreo de 16 bits por canal.

    Parametros:
    ficCod -- archivo mono de 32 bits codificado
    ficEste -- archivo de salida estéreo reconstruido
    """
    with open(ficCod, 'rb') as f_in:
        cab = leer_cabecera_wave(f_in)
        if cab['num_channels'] != 1 or cab['bits_per_sample'] != 32:
            raise ValueError('El fichero debe ser monofónico de 32 bits')
        datos = f_in.read(cab['data_size'])

    muestras = [struct.unpack('<I', datos[i:i+4])[0] for i in range(0, len(datos), 4)]
    reconstruidas = [
        struct.pack('<hh',
            saturar16((m >> 16) + int16(m & 0xFFFF)),
            saturar16((m >> 16) - int16(m & 0xFFFF))
        ) for m in muestras
    ]
    datos_estereo = b''.join(reconstruidas)

    with open(ficEste, 'wb') as f_out:
        escribir_cabecera_wave(f_out, 2, cab['sample_rate'], 16, len(datos_estereo))
        f_out.write(datos_estereo)
