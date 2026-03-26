#!/usr/bin/env python3

import paramiko
import sys
import os
import smtplib
import subprocess
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

DEVICES_FILE = "/home/ubuntu/lab1_cloud/dispositivos.txt"
SSH_PORT = 22
SSH_TIMEOUT = 10
CONNECTION_TIMEOUT = 10
SSH_USER = "ubuntu"
SSH_PASSWORD = "ubuntu"

CORREO_ORIGEN = "editoriallaroca@gmail.com"
CONTRASENA_APP = "xnvq rncf mtvf hnqd"
CORREO_DESTINO = "jbzambrano@pucp.edu.pe"
CORREO_CC = "jbzambrano@pucp.edu.pe"
CODIGO_ALUMNO = "20193265"
SERVIDOR_SMTP = "smtp.gmail.com"
PUERTO_SMTP = 587
RED_GESTION = "10.0.10"


class BillingMonitor:
    
    def __init__(self, username, password, timeout=10):
        self.username = username
        self.password = password
        self.timeout = timeout
        self.ssh_clients = {}
        self.resultados = []
    
    def ping_host(self, host):
        try:
            resultado = subprocess.run(
                ["ping", "-c", "1", "-W", "2", host],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            return resultado.returncode == 0
        except Exception:
            return False
    
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
            return False
        except paramiko.ssh_exception.NoValidConnectionsError:
            print(f"[ERROR - CONECTIVIDAD]")
            return False
        except paramiko.ssh_exception.SSHException as e:
            print(f"[ERROR - SSH]")
            return False
        except Exception as e:
            print(f"[ERROR - GENERAL]")
            return False
    
    def execute_remote_command(self, host, command):
        if host not in self.ssh_clients:
            return None, "No conectado", -1
        
        try:
            client = self.ssh_clients[host]
            stdin, stdout, stderr = client.exec_command(command, timeout=self.timeout)
            
            output = stdout.read().decode('utf-8', errors='ignore')
            error = stderr.read().decode('utf-8', errors='ignore')
            return_code = stdout.channel.recv_exit_status()
            
            return output, error, return_code
            
        except Exception as e:
            return None, str(e), -1
    
    def get_hostname(self, host):
        if host not in self.ssh_clients:
            return "DESCONOCIDO"
        
        output, error, return_code = self.execute_remote_command(host, "hostname")
        
        if return_code == 0 and output:
            return output.strip()
        return "DESCONOCIDO"
    
    def get_interface_en_red_gestion(self, host):
        if host not in self.ssh_clients:
            return None
        
        comando = f"ip addr show | grep 'inet {RED_GESTION}' -B 5 | grep -o '^[0-9]*: [a-zA-Z0-9]*' | awk '{{print $2}}' | head -1"
        output, error, return_code = self.execute_remote_command(host, comando)
        
        if return_code == 0 and output:
            interfaz = output.strip()
            if interfaz:
                return interfaz
        
        return None
    
    def get_bytes_interface(self, host, interfaz):
        if host not in self.ssh_clients:
            return None, None
        
        comando = f"ip -s link show {interfaz} | grep -A 1 'RX:' | tail -1 | awk '{{print $1, $2}}'"
        output, error, return_code = self.execute_remote_command(host, comando)
        
        if return_code != 0:
            return None, None
        
        try:
            partes = output.strip().split()
            if len(partes) >= 2:
                bytes_recibidos = partes[0]
                bytes_transmitidos = partes[1]
                return bytes_transmitidos, bytes_recibidos
        except Exception:
            pass
        
        return None, None
    
    def recolectar_estadisticas(self, nombre_servidor, ip_servidor):
        print(f"\n[*] Procesando {nombre_servidor} ({ip_servidor})...")
        
        disponible = self.ping_host(ip_servidor)
        
        if not disponible:
            print(f"    [OFFLINE] No responde a ping")
            self.resultados.append({
                'hostname': nombre_servidor,
                'ip': ip_servidor,
                'interfaz': 'N/A',
                'bytes_tx': 'N/A',
                'bytes_rx': 'N/A',
                'estado': 'OFFLINE'
            })
            return
        
        if not self.connect(ip_servidor, port=SSH_PORT):
            print(f"    [ERROR] Fallo SSH")
            self.resultados.append({
                'hostname': nombre_servidor,
                'ip': ip_servidor,
                'interfaz': 'N/A',
                'bytes_tx': 'N/A',
                'bytes_rx': 'N/A',
                'estado': 'SSH_ERROR'
            })
            return
        
        hostname = self.get_hostname(ip_servidor)
        print(f"    [OK] Hostname: {hostname}")
        
        interfaz = self.get_interface_en_red_gestion(ip_servidor)
        
        if not interfaz:
            print(f"    [WARNING] Interfaz no encontrada en {RED_GESTION}.0/24")
            self.resultados.append({
                'hostname': hostname,
                'ip': ip_servidor,
                'interfaz': 'NO ENCONTRADA',
                'bytes_tx': 'N/A',
                'bytes_rx': 'N/A',
                'estado': 'INTERFAZ_DOWN'
            })
            return
        
        print(f"    [OK] Interfaz: {interfaz}")
        
        bytes_tx, bytes_rx = self.get_bytes_interface(ip_servidor, interfaz)
        
        if bytes_tx is None or bytes_rx is None:
            print(f"    [WARNING] No hay estadísticas")
            estado = "DOWN"
        else:
            print(f"    [OK] TX: {bytes_tx} | RX: {bytes_rx}")
            estado = "ONLINE"
        
        self.resultados.append({
            'hostname': hostname,
            'ip': ip_servidor,
            'interfaz': interfaz,
            'bytes_tx': bytes_tx if bytes_tx else 'N/A',
            'bytes_rx': bytes_rx if bytes_rx else 'N/A',
            'estado': estado
        })
    
    def generar_html(self):
        html = """<html>
<head>
<meta charset="UTF-8">
<style>
body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
h1 { color: #333; }
h2 { color: #666; margin-top: 20px; }
table { border-collapse: collapse; width: 100%; margin-top: 10px; background: white; }
th { background-color: #4CAF50; color: white; padding: 12px; text-align: left; border: 1px solid #ddd; }
td { padding: 10px; border: 1px solid #ddd; }
tr:nth-child(even) { background-color: #f9f9f9; }
.online { color: green; font-weight: bold; }
.offline { color: red; font-weight: bold; }
.down { color: orange; font-weight: bold; }
.footer { margin-top: 30px; font-size: 12px; color: #999; }
</style>
</head>
<body>
"""
        
        html += f"<h1>Reporte de Transferencia de Datos - Billing AWS</h1>"
        html += f"<p><strong>Fecha y Hora:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
        html += f"<p><strong>Red de Gestión:</strong> {RED_GESTION}.0/24</p>"
        
        html += "<h2>Estadísticas por Servidor</h2>"
        html += "<table>"
        html += "<tr>"
        html += "<th>HOSTNAME DEL EQUIPO REMOTO</th>"
        html += "<th>INTERFAZ DEL EQUIPO REMOTO</th>"
        html += "<th>BYTES TRANSFERIDOS</th>"
        html += "<th>BYTES RECIBIDOS</th>"
        html += "<th>ESTADO</th>"
        html += "</tr>"
        
        for r in self.resultados:
            if r['estado'] == "ONLINE":
                clase, display = "online", "ONLINE"
            elif r['estado'] == "OFFLINE":
                clase, display = "offline", "OFFLINE"
            else:
                clase, display = "down", r['estado']
            
            html += "<tr>"
            html += f"<td>{r['hostname']}</td>"
            html += f"<td>{r['interfaz']}</td>"
            html += f"<td>{r['bytes_tx']}</td>"
            html += f"<td>{r['bytes_rx']}</td>"
            html += f"<td class='{clase}'>{display}</td>"
            html += "</tr>"
        
        html += "</table>"
        html += f"<div class='footer'><p>Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p></div>"
        html += """</body></html>"""
        
        return html
    
    def enviar_correo(self):
        try:
            print("\n[*] Preparando correo...")
            
            asunto = f"LAB1_TEL141_2024-2_{CODIGO_ALUMNO}"
            cuerpo_html = self.generar_html()
            
            mensaje = MIMEMultipart('alternative')
            mensaje['From'] = CORREO_ORIGEN
            mensaje['To'] = CORREO_DESTINO
            mensaje['Cc'] = CORREO_CC
            mensaje['Subject'] = asunto
            
            parte_html = MIMEText(cuerpo_html, 'html', 'UTF-8')
            mensaje.attach(parte_html)
            
            print(f"[*] Conectando SMTP {SERVIDOR_SMTP}:{PUERTO_SMTP}...")
            
            servidor = smtplib.SMTP(SERVIDOR_SMTP, PUERTO_SMTP)
            servidor.starttls()
            
            print(f"[*] Autenticando...")
            servidor.login(CORREO_ORIGEN, CONTRASENA_APP)
            
            destinatarios = [CORREO_DESTINO, CORREO_CC]
            
            print(f"[*] Enviando correo...")
            servidor.sendmail(CORREO_ORIGEN, destinatarios, mensaje.as_string())
            
            servidor.quit()
            
            print(f"[OK] Correo enviado")
            print(f"    Asunto: {asunto}")
            print(f"    Para: {CORREO_DESTINO}")
            print(f"    CC: {CORREO_CC}")
            return True
            
        except smtplib.SMTPAuthenticationError:
            print(f"[ERROR] Fallo autenticación Gmail")
            return False
        except smtplib.SMTPException as e:
            print(f"[ERROR] SMTP: {str(e)}")
            return False
        except Exception as e:
            print(f"[ERROR] Correo: {str(e)}")
            return False
    
    def close_all(self):
        for host in list(self.ssh_clients.keys()):
            try:
                self.ssh_clients[host].close()
            except:
                pass


def load_devices(filepath):
    if not os.path.exists(filepath):
        print(f"[ERROR] Archivo no encontrado: {filepath}")
        return None
    
    devices = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split()
                if len(parts) >= 2:
                    devices.append((parts[0], parts[1]))
        
        return devices if devices else None
        
    except Exception as e:
        print(f"[ERROR] Lectura dispositivos: {str(e)}")
        return None


def main():
    
    print("=" * 70)
    print("MONITOR DE BILLING - TRANSFERENCIA DE BYTES")
    print("=" * 70)
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    print(f"[*] Cargando dispositivos desde {DEVICES_FILE}...")
    devices = load_devices(DEVICES_FILE)
    
    if not devices:
        print("[ERROR] No hay dispositivos")
        sys.exit(1)
    
    print(f"[OK] Se cargaron {len(devices)} dispositivo(s)")
    print()
    
    monitor = BillingMonitor(SSH_USER, SSH_PASSWORD, timeout=CONNECTION_TIMEOUT)
    
    print("[*] Validando disponibilidad...")
    print("-" * 70)
    
    for nombre, ip in devices:
        disponible = monitor.ping_host(ip)
        estado = "OK" if disponible else "OFFLINE"
        print(f"    {nombre} ({ip}): {estado}")
    
    print()
    print("[*] Recolectando estadísticas...")
    print("-" * 70)
    
    for nombre, ip in devices:
        monitor.recolectar_estadisticas(nombre, ip)
    
    print()
    print("[*] Resumen")
    print("-" * 70)
    
    for r in monitor.resultados:
        print(f"{r['hostname']:<15} | {r['interfaz']:<10} | TX: {str(r['bytes_tx']):<12} | RX: {str(r['bytes_rx']):<12} | {r['estado']}")
    
    print()
    print("[*] Enviando correo...")
    print("-" * 70)
    
    if monitor.enviar_correo():
        print("\n[OK] Proceso completo")
    else:
        print("\n[ERROR] Fallo al enviar")
    
    monitor.close_all()
    
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Interrumpido")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
