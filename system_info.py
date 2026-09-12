#!/usr/bin/env python3
"""
Script de Diagnóstico do Sistema
Verifica todas as configurações do PC
"""

import os
import platform
import subprocess
import socket
import json
import datetime
import sys

def run_cmd(cmd):
    """Executa comando e retorna saída"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=True)
        return result.stdout.strip() if result.stdout else "N/A"
    except Exception as e:
        return f"Erro: {e}"

def separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def system_info():
    separator("🖥️  INFORMAÇÕES DO SISTEMA OPERACIONAL")
    print(f"  Sistema Operacional : {platform.system()}")
    print(f"  Versão              : {platform.version()}")
    print(f"  Release             : {platform.release()}")
    print(f"  Arquitetura         : {platform.machine()}")
    print(f"  Processador         : {platform.processor()}")
    print(f"  Nome do PC          : {platform.node()}")
    print(f"  Usuário Atual       : {os.getenv('USERNAME', 'N/A')}")
    print(f"  Diretório Atual     : {os.getcwd()}")

def cpu_info():
    separator("🧠 INFORMAÇÕES DA CPU")
    # WMIC CPU
    cpu_name = run_cmd("wmic cpu get Name /value")
    cpu_cores = run_cmd("wmic cpu get NumberOfCores /value")
    cpu_threads = run_cmd("wmic cpu get NumberOfLogicalProcessors /value")
    cpu_maxclock = run_cmd("wmic cpu get MaxClockSpeed /value")
    cpu_status = run_cmd("wmic cpu get Status /value")
    
    print(f"  Processador         : {cpu_name.replace('Name=', '') if 'Name=' in cpu_name else cpu_name}")
    print(f"  Núcleos (Físicos)   : {cpu_cores.replace('NumberOfCores=', '') if 'NumberOfCores=' in cpu_cores else cpu_cores}")
    print(f"  Threads (Lógicos)   : {cpu_threads.replace('NumberOfLogicalProcessors=', '') if 'NumberOfLogicalProcessors=' in cpu_threads else cpu_threads}")
    print(f"  Clock Máximo        : {cpu_maxclock.replace('MaxClockSpeed=', '') if 'MaxClockSpeed=' in cpu_maxclock else cpu_maxclock} MHz")
    print(f"  Status              : {cpu_status.replace('Status=', '') if 'Status=' in cpu_status else cpu_status}")

def memory_info():
    separator("💾 INFORMAÇÕES DE MEMÓRIA RAM")
    # Memória total e disponível
    mem_info = run_cmd("wmic OS get TotalVisibleMemorySize,FreePhysicalMemory /value")
    print(f"  {mem_info}")
    
    # Detalhes dos pentes de memória
    mem_details = run_cmd("wmic memorychip get Capacity,Speed,Manufacturer,PartNumber,DeviceLocator /format:list")
    if mem_details and mem_details != "N/A":
        print("\n  Detalhes dos Pentes:")
        sticks = mem_details.split("\n\n")
        for i, stick in enumerate(sticks, 1):
            if stick.strip():
                print(f"\n  Pente {i}:")
                for line in stick.strip().split("\n"):
                    if line.strip() and "=" in line:
                        key, val = line.strip().split("=", 1)
                        key_map = {
                            "Capacity": "Capacidade",
                            "Speed": "Velocidade",
                            "Manufacturer": "Fabricante",
                            "PartNumber": "Modelo",
                            "DeviceLocator": "Slot"
                        }
                        if key in key_map:
                            if key == "Capacity" and val:
                                val = f"{int(val) // 1048576} GB"
                            print(f"    {key_map[key]:15s}: {val}")

def disk_info():
    separator("💿 INFORMAÇÕES DE DISCO")
    # Discos lógicos
    disks = run_cmd("wmic logicaldisk get DeviceID,Size,FreeSpace,FileSystem,VolumeName,DriveType /format:list")
    if disks and disks != "N/A":
        entries = disks.split("\n\n")
        for entry in entries:
            if entry.strip():
                info = {}
                for line in entry.strip().split("\n"):
                    if "=" in line:
                        key, val = line.strip().split("=", 1)
                        info[key] = val
                
                dtype = {"0": "Desconhecido", "1": "Removível", "2": "Local", "3": "Rede", "4": "CD-ROM", "5": "RAM"}
                drive_type = dtype.get(info.get("DriveType", "0"), "Desconhecido")
                size_gb = f"{int(info.get('Size', 0)) // 1073741824} GB" if info.get('Size') else "N/A"
                free_gb = f"{int(info.get('FreeSpace', 0)) // 1073741824} GB" if info.get('FreeSpace') else "N/A"
                used_pct = ""
                if info.get('Size') and info.get('FreeSpace'):
                    total = int(info['Size'])
                    free = int(info['FreeSpace'])
                    pct = ((total - free) / total) * 100
                    used_pct = f"({pct:.1f}% usado)"
                
                print(f"\n  Unidade: {info.get('DeviceID', 'N/A')} [{drive_type}]")
                print(f"    Rótulo      : {info.get('VolumeName', 'N/A')}")
                print(f"    Sistema     : {info.get('FileSystem', 'N/A')}")
                print(f"    Total       : {size_gb}")
                print(f"    Livre       : {free_gb} {used_pct}")
    
    # Discos físicos
    separator("💿 DISCOS FÍSICOS")
    phys_disks = run_cmd("wmic diskdrive get Model,Size,MediaType,InterfaceType /format:list")
    if phys_disks and phys_disks != "N/A":
        entries = phys_disks.split("\n\n")
        for i, entry in enumerate(entries, 1):
            if entry.strip():
                info = {}
                for line in entry.strip().split("\n"):
                    if "=" in line:
                        key, val = line.strip().split("=", 1)
                        info[key] = val
                size_gb = f"{int(info.get('Size', 0)) // 1073741824} GB" if info.get('Size') else "N/A"
                print(f"\n  Disco {i}:")
                print(f"    Modelo     : {info.get('Model', 'N/A')}")
                print(f"    Tipo       : {info.get('MediaType', 'N/A')}")
                print(f"    Interface  : {info.get('InterfaceType', 'N/A')}")
                print(f"    Tamanho    : {size_gb}")

def gpu_info():
    separator("🎮 INFORMAÇÕES DE GPU")
    gpus = run_cmd("wmic path win32_videocontroller get Name,AdapterRAM,DriverVersion,DriverDate,VideoProcessor /format:list")
    if gpus and gpus != "N/A":
        entries = gpus.split("\n\n")
        for i, entry in enumerate(entries, 1):
            if entry.strip():
                info = {}
                for line in entry.strip().split("\n"):
                    if "=" in line:
                        key, val = line.strip().split("=", 1)
                        info[key] = val
                
                ram_mb = ""
                if info.get('AdapterRAM'):
                    try:
                        ram_mb = f"{int(info['AdapterRAM']) // 1048576} MB"
                    except:
                        ram_mb = "N/A"
                
                print(f"\n  GPU {i}:")
                print(f"    Nome           : {info.get('Name', 'N/A')}")
                print(f"    Processador    : {info.get('VideoProcessor', 'N/A')}")
                print(f"    VRAM           : {ram_mb}")
                print(f"    Driver Versão  : {info.get('DriverVersion', 'N/A')}")
                print(f"    Driver Data    : {info.get('DriverDate', 'N/A')}")

def network_info():
    separator("🌐 INFORMAÇÕES DE REDE")
    # Hostname e IP
    hostname = socket.gethostname()
    print(f"  Hostname          : {hostname}")
    
    try:
        local_ip = socket.gethostbyname(hostname)
        print(f"  IP Local          : {local_ip}")
    except:
        print(f"  IP Local          : N/A")
    
    # Adaptadores de rede
    adapters = run_cmd("wmic nic get Name,NetConnectionID,Speed,NetConnectionStatus,MACAddress /format:list")
    if adapters and adapters != "N/A":
        entries = adapters.split("\n\n")
        for entry in entries:
            if entry.strip():
                info = {}
                for line in entry.strip().split("\n"):
                    if "=" in line:
                        key, val = line.strip().split("=", 1)
                        info[key] = val
                
                status_map = {"0": "Desconectado", "1": "Conectado", "2": "Desconectado"}
                status = status_map.get(info.get('NetConnectionStatus', '0'), info.get('NetConnectionStatus', 'N/A'))
                speed = info.get('Speed', 'N/A')
                if speed and speed != 'N/A':
                    try:
                        speed = f"{int(speed) / 1000000:.0f} Mbps"
                    except:
                        pass
                
                if info.get('NetConnectionID'):
                    print(f"\n  Adaptador: {info.get('NetConnectionID', 'N/A')}")
                    print(f"    Nome        : {info.get('Name', 'N/A')}")
                    print(f"    MAC         : {info.get('MACAddress', 'N/A')}")
                    print(f"    Velocidade  : {speed}")
                    print(f"    Status      : {status}")

def motherboard_info():
    separator("🔧 INFORMAÇÕES DA PLACA-MÃE")
    mb_manufacturer = run_cmd("wmic baseboard get Manufacturer /value")
    mb_product = run_cmd("wmic baseboard get Product /value")
    mb_version = run_cmd("wmic baseboard get Version /value")
    mb_serial = run_cmd("wmic baseboard get SerialNumber /value")
    
    print(f"  Fabricante : {mb_manufacturer.replace('Manufacturer=', '') if 'Manufacturer=' in mb_manufacturer else mb_manufacturer}")
    print(f"  Produto    : {mb_product.replace('Product=', '') if 'Product=' in mb_product else mb_product}")
    print(f"  Versão     : {mb_version.replace('Version=', '') if 'Version=' in mb_version else mb_version}")
    print(f"  Serial     : {mb_serial.replace('SerialNumber=', '') if 'SerialNumber=' in mb_serial else mb_serial}")
    
    # BIOS
    separator("🔧 INFORMAÇÕES DA BIOS")
    bios_vendor = run_cmd("wmic bios get Manufacturer /value")
    bios_version = run_cmd("wmic bios get SMBIOSBIOSVersion /value")
    bios_date = run_cmd("wmic bios get ReleaseDate /value")
    
    print(f"  Fabricante : {bios_vendor.replace('Manufacturer=', '') if 'Manufacturer=' in bios_vendor else bios_vendor}")
    print(f"  Versão     : {bios_version.replace('SMBIOSBIOSVersion=', '') if 'SMBIOSBIOSVersion=' in bios_version else bios_version}")
    print(f"  Data       : {bios_date.replace('ReleaseDate=', '') if 'ReleaseDate=' in bios_date else bios_date}")

def battery_info():
    separator("🔋 INFORMAÇÕES DA BATERIA")
    battery = run_cmd("wmic path win32_battery get EstimatedChargeRemaining,BatteryStatus,Name /format:list")
    if battery and battery.strip() and battery != "N/A":
        print(f"  {battery}")
    else:
        print("  Nenhuma bateria detectada (Desktop ou não disponível)")

def startup_info():
    separator("🚀 PROGRAMAS DE INICIALIZAÇÃO")
    startup = run_cmd("wmic startup get Caption,Command,Location /format:list")
    if startup and startup != "N/A":
        entries = startup.split("\n\n")
        for entry in entries:
            if entry.strip():
                info = {}
                for line in entry.strip().split("\n"):
                    if "=" in line:
                        key, val = line.strip().split("=", 1)
                        info[key] = val
                if info.get('Caption'):
                    print(f"  • {info.get('Caption', 'N/A')}")
                    print(f"    Comando : {info.get('Command', 'N/A')}")
                    print(f"    Local   : {info.get('Location', 'N/A')}")
                    print()

def processes_info():
    separator("⚙️  TOP 15 PROCESSOS POR MEMÓRIA")
    result = run_cmd('powershell -Command "Get-Process | Sort-Object -Property WorkingSet64 -Descending | Select-Object -First 15 Name, @{Name=\'Memory_MB\';Expression={[math]::Round($_.WorkingSet64/1048576,2)}}, CPU, Id | Format-Table -AutoSize"')
    print(result)

def installed_software():
    separator("📦 SOFTWARES INSTALADOS (últimos 30)")
    software = run_cmd('powershell -Command "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | Where-Object DisplayName | Select-Object DisplayName, DisplayVersion, Publisher, InstallDate | Sort-Object DisplayName | Select-Object -First 30 | Format-Table -AutoSize"')
    print(software)

def environment_info():
    separator("🌍 VARIÁVEIS DE AMBIENTE IMPORTANTES")
    important_vars = [
        'COMPUTERNAME', 'USERNAME', 'USERPROFILE', 'HOMEPATH', 'HOMEDRIVE',
        'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATH', 'PROCESSOR_ARCHITECTURE',
        'NUMBER_OF_PROCESSORS', 'OS', 'PUBLIC', 'PROGRAMFILES', 'PROGRAMFILES(X86)',
        'SYSTEMDRIVE', 'COMSPEC', 'PATHEXT'
    ]
    for var in important_vars:
        val = os.environ.get(var, 'N/A')
        if var == 'PATH':
            paths = val.split(';')
            print(f"  {var}:")
            for p in paths[:10]:
                if p:
                    print(f"    - {p}")
            if len(paths) > 10:
                print(f"    ... e mais {len(paths)-10} entradas")
        else:
            print(f"  {var:25s}: {val}")

def uptime_info():
    separator("⏱️  INFORMAÇÕES DE UPTIME")
    uptime = run_cmd('powershell -Command "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime"')
    print(f"  Último Boot: {uptime}")
    
    uptime_diff = run_cmd('powershell -Command "(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime | Select-Object Days,Hours,Minutes | Format-List"')
    print(f"  Tempo Ligado:\n  {uptime_diff}")

def security_info():
    separator("🛡️  INFORMAÇÕES DE SEGURANÇA")
    # Antivírus
    av = run_cmd('powershell -Command "Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntivirusProduct | Select-Object displayName, productState | Format-List"')
    print(f"  Antivírus:\n  {av}")
    
    # Firewall
    fw = run_cmd('netsh advfirewall show allprofiles state')
    print(f"  Firewall:\n  {fw}")

def main():
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║        🔍 DIAGNÓSTICO COMPLETO DO SISTEMA 🔍          ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Data/Hora: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Python: {sys.version.split()[0]}")
    
    system_info()
    cpu_info()
    memory_info()
    disk_info()
    gpu_info()
    motherboard_info()
    network_info()
    battery_info()
    uptime_info()
    security_info()
    startup_info()
    processes_info()
    installed_software()
    environment_info()
    
    print(f"\n{'='*60}")
    print(f"  ✅ Diagnóstico concluído com sucesso!")
    print(f"  📅 {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()