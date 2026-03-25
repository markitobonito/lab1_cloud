#!/usr/bin/env python3
import paramiko
import sys
import os
from datetime import datetime
from pathlib import Path
DEVICES_FILE = "/home/ubuntu/lab1_cloud/dispositivos.txt"
SSH_PORT = 22
SSH_TIMEOUT = 10
CONNECTION_TIMEOUT = 10
SSH_USER = "ubuntu"
SSH_PASSWORD = "ubuntu"
class NetworkCollector:
    def __init__(self, username, password, timeout=10):
        self.username = username
        self.password = password
        self.timeout = timeout
        self.ssh_clients = {}
    def connect(self, host, port=22):
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            print(f"[*] Conectando a {host}:{port}...", end=" ")
            client.connect(
                hostname=host,
                port=port,
                username=self.username,
                password=self.password,
                timeout=self.timeout,
                allow_agent=False,
                look_for_keys=False
            )
            print("[OK]")
            self.ssh_clients[host] = client
            return True
        except paramiko.ssh_exception.AuthenticationException:
            print(f"[ERROR - AUTENTICACIÓN]")
            print(f"  └─ Usuario/contraseña incorrectos para {host}")
            return False
        except paramiko.ssh_exception.NoValidConnectionsError:
            print(f"[ERROR - CONECTIVIDAD]")
            print(f"  └─ No se puede alcanzar {host} (host inaccesible)")
            return False
        except paramiko.ssh_exception.SSHException as e:
            print(f"[ERROR - SSH]")
            print(f"  └─ {str(e)}")
            return False
        except Exception as e:
            print(f"[ERROR - GENERAL]")
            print(f"  └─ {str(e)}")
            return False
    def execute_remote_command(self, host, command):
        if host not in self.ssh_clients:
            return None, "No conectado a este host", -1
        try:
            client = self.ssh_clients[host]
            stdin, stdout, stderr = client.exec_command(command, timeout=self.timeout)
            output = stdout.read().decode('utf-8', errors='ignore')
            error = stderr.read().decode('utf-8', errors='ignore')
            return_code = stdout.channel.recv_exit_status()
            return output, error, return_code
        except paramiko.ssh_exception.SSHException as e:
            return None, f"Error SSH: {str(e)}", -1
        except Exception as e:
            return None, f"Error remoto: {str(e)}", -1
    def get_interfaces_info(self, host):
        if host not in self.ssh_clients:
            return None
        command = "ip -br addr show | tail -n +1"
        output, error, return_code = self.execute_remote_command(host, command)
        if return_code != 0 or output is None:
            print(f"  [ERROR] No se pudieron obtener interfaces: {error}")
            return None
        interfaces = []
        lines = output.strip().split('\n')
        for index, line in enumerate(lines, 1):
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            ifname = parts[0]
            state = parts[1]
            ip_list = parts[2:] if len(parts) > 2 else []
            if ip_list:
                for ip in ip_list:
                    if ':' not in ip or '.' in ip:
                        interfaces.append((index, ifname, ip, state))
                        break
            else:
                interfaces.append((index, ifname, "N/A", state))
        return interfaces
    def get_hostname(self, host):
        if host not in self.ssh_clients:
            return host
        output, error, return_code = self.execute_remote_command(host, "hostname")
        if return_code == 0 and output:
            return output.strip()
        return host
    def close_connection(self, host):
        if host in self.ssh_clients:
            self.ssh_clients[host].close()
            del self.ssh_clients[host]
    def close_all(self):
        for host in list(self.ssh_clients.keys()):
            self.close_connection(host)
def load_devices(filepath):
    if not os.path.exists(filepath):
        print(f"[ERROR] Archivo no encontrado: {filepath}")
        return None
    devices = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    ip = parts[1]
                    devices.append((name, ip))
        if not devices:
            print(f"[ERROR] No se encontraron dispositivos en {filepath}")
            return None
        return devices
    except Exception as e:
        print(f"[ERROR] Error al leer archivo: {str(e)}")
        return None
def print_results(results):
    for server_name, data in results.items():
        if data['status'] == 'error':
            print(f"\n{server_name}:")
            print(f"[ERROR] {data['error']}")
            continue
        print(f"\n{server_name}:")
        print(f"{'INDEX':<8}{'IFNAME':<12}{'IP':<20}{'STATE':<10}")
        print("-" * 50)
        for index, ifname, ip, state in data['interfaces']:
            print(f"{index:<8}{ifname:<12}{ip:<20}{state:<10}")
def main():
    print("=" * 60)
    print("RECOLECTOR DE INFORMACIÓN DE INTERFACES DE RED")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print(f"[*] Cargando dispositivos desde {DEVICES_FILE}...")
    devices = load_devices(DEVICES_FILE)
    if not devices:
        print("[ERROR] No se pudieron cargar los dispositivos")
        sys.exit(1)
    print(f"[OK] Se cargaron {len(devices)} dispositivo(s)")
    print()
    collector = NetworkCollector(SSH_USER, SSH_PASSWORD, timeout=CONNECTION_TIMEOUT)
    print("[*] Fase 1: Conectando a servidores...")
    print("-" * 60)
    connected_devices = []
    for name, ip in devices:
        if collector.connect(ip, port=SSH_PORT):
            connected_devices.append((name, ip))
        else:
            print(f"  ⚠ {name} ({ip}) - Saltando este servidor")
    if not connected_devices:
        print("\n[ERROR] No se pudo conectar a ningún servidor")
        sys.exit(1)
    print(f"\n[OK] Conectado a {len(connected_devices)} servidor(s)")
    print()
    print("[*] Fase 2: Recolectando información de interfaces...")
    print("-" * 60)
    results = {}
    for name, ip in connected_devices:
        print(f"[*] Obteniendo interfaces de {name} ({ip})...", end=" ")
        interfaces = collector.get_interfaces_info(ip)
        if interfaces is None:
            print("[FALLÓ]")
            results[name] = {
                'status': 'error',
                'error': 'No se pudieron obtener interfaces',
                'ip': ip
            }
        else:
            print(f"[OK] {len(interfaces)} interfaz(es)")
            results[name] = {
                'status': 'success',
                'interfaces': interfaces,
                'ip': ip
            }
    print()
    print("[*] Fase 3: Resultado de la recolección")
    print("=" * 60)
    print_results(results)
    collector.close_all()
    print()
    print("[OK] Todas las conexiones cerradas")
    print("=" * 60)
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Script interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR CRÍTICO] {str(e)}")
        sys.exit(1)