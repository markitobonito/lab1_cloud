#!/bin/bash

SELECTED_INTERFACE=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' 
list_interfaces() {
    clear
    echo -e "${BLUE}=== LISTADO DE INTERFACES DE RED ===${NC}"
    echo ""
    ip -br addr show 2>/dev/null | while read iface state ip rest; do
        if [ "$iface" != "lo" ]; then
            echo -e "${GREEN}Interfaz: ${NC}$iface"
            echo -e "${GREEN}Estado: ${NC}$state"
            if [ -n "$ip" ]; then
                echo -e "${GREEN}IPs configuradas:${NC}"
                ip addr show "$iface" 2>/dev/null | grep -oP 'inet\K[^/]*' | while read ipaddr; do
                    echo "  - $ipaddr"
                done
            else
                echo -e "${YELLOW}Sin direcciones IP asignadas${NC}"
            fi
            echo ""
        fi
    done
    read -p "Presiona ENTER para continuar..."
}
select_interface() {
    clear
    echo -e "${BLUE}=== SELECCIONAR INTERFAZ ===${NC}"
    echo ""
    local interfaces=($(ip -br addr show 2>/dev/null | awk '{print $1}' | grep -v lo))
    if [ ${
        echo -e "${RED}No se encontraron interfaces de red${NC}"
        read -p "Presiona ENTER para continuar..."
        return 1
    fi
    echo "Interfaces disponibles:"
    for i in "${!interfaces[@]}"; do
        echo "$((i+1)). ${interfaces[$i]}"
    done
    echo ""
    read -p "Selecciona el número de la interfaz: " choice
    if [ "$choice" -ge 1 ] && [ "$choice" -le ${
        SELECTED_INTERFACE="${interfaces[$((choice-1))]}"
        echo -e "${GREEN}Interfaz seleccionada: $SELECTED_INTERFACE${NC}"
        read -p "Presiona ENTER para continuar..."
        return 0
    else
        echo -e "${RED}Opción inválida${NC}"
        read -p "Presiona ENTER para continuar..."
        return 1
    fi
}
flush_interface_ips() {
    clear
    if [ -z "$SELECTED_INTERFACE" ]; then
        echo -e "${RED}Primero debes seleccionar una interfaz (Opción 2)${NC}"
        read -p "Presiona ENTER para continuar..."
        return 1
    fi
    echo -e "${BLUE}=== LIMPIAR IPs DE LA INTERFAZ ===${NC}"
    echo "Interfaz seleccionada: $SELECTED_INTERFACE"
    echo ""
    echo -e "${YELLOW}IPs actuales:${NC}"
    ip addr show "$SELECTED_INTERFACE" 2>/dev/null | grep -oP 'inet\K[^/]*' | while read ipaddr; do
        echo "  - $ipaddr"
    done
    echo ""
    read -p "¿Confirmas que deseas eliminar todas las IPs? (s/n): " confirm
    if [ "$confirm" = "s" ] || [ "$confirm" = "S" ]; then
        sudo ip address flush dev "$SELECTED_INTERFACE" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}IPs eliminadas correctamente${NC}"
        else
            echo -e "${RED}Error al eliminar IPs. ¿Ejecutas con permisos de administrador?${NC}"
        fi
    else
        echo "Operación cancelada"
    fi
    read -p "Presiona ENTER para continuar..."
}
validate_cidr() {
    local cidr=$1
    if [[ ! $cidr =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$ ]]; then
        return 1
    fi
    local ip="${cidr%/*}"
    local mask="${cidr
    local IFS='.'
    local -a octets=($ip)
    for octet in "${octets[@]}"; do
        if [ "$octet" -gt 255 ] || [ "$octet" -lt 0 ]; then
            return 1
        fi
    done
    if [ "$mask" -gt 32 ] || [ "$mask" -lt 0 ]; then
        return 1
    fi
    return 0
}
add_or_replace_ip() {
    clear
    if [ -z "$SELECTED_INTERFACE" ]; then
        echo -e "${RED}Primero debes seleccionar una interfaz (Opción 2)${NC}"
        read -p "Presiona ENTER para continuar..."
        return 1
    fi
    echo -e "${BLUE}=== AGREGAR O REEMPLAZAR IP ===${NC}"
    echo "Interfaz seleccionada: $SELECTED_INTERFACE"
    echo ""
    echo -e "${YELLOW}IPs actuales:${NC}"
    local current_ips=$(ip addr show "$SELECTED_INTERFACE" 2>/dev/null | grep -oP 'inet\K[^/]*')
    if [ -n "$current_ips" ]; then
        echo "$current_ips" | while read ipaddr; do
            echo "  - $ipaddr"
        done
    else
        echo "  Sin IPs asignadas"
    fi
    echo ""
    read -p "Ingresa la IP en formato CIDR (ej: 192.168.1.10/24): " new_ip
    if ! validate_cidr "$new_ip"; then
        echo -e "${RED}Error: Formato CIDR inválido${NC}"
        read -p "Presiona ENTER para continuar..."
        return 1
    fi
    echo ""
    echo "Opciones:"
    echo "1. Agregar la IP a las existentes"
    echo "2. Reemplazar todas las IPs"
    read -p "Elige una opción (1 o 2): " mode
    if [ "$mode" = "2" ]; then
        sudo ip address flush dev "$SELECTED_INTERFACE" 2>/dev/null
        if [ $? -ne 0 ]; then
            echo -e "${RED}Error al limpiar las IPs. Verifica permisos.${NC}"
            read -p "Presiona ENTER para continuar..."
            return 1
        fi
    fi
    sudo ip address add "$new_ip" dev "$SELECTED_INTERFACE" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}IP agregada/reemplazada correctamente: $new_ip${NC}"
    else
        echo -e "${RED}Error al agregar la IP. Verifica permisos.${NC}"
    fi
    read -p "Presiona ENTER para continuar..."
}
bring_up_interface() {
    clear
    if [ -z "$SELECTED_INTERFACE" ]; then
        echo -e "${RED}Primero debes seleccionar una interfaz (Opción 2)${NC}"
        read -p "Presiona ENTER para continuar..."
        return 1
    fi
    echo -e "${BLUE}=== ENCENDER INTERFAZ ===${NC}"
    echo "Interfaz seleccionada: $SELECTED_INTERFACE"
    echo ""
    local state=$(ip -br addr show "$SELECTED_INTERFACE" 2>/dev/null | awk '{print $2}')
    if [ "$state" = "UP" ]; then
        echo -e "${YELLOW}La interfaz ya está activa (UP)${NC}"
    else
        echo "Encendiendo interfaz..."
        sudo ip link set dev "$SELECTED_INTERFACE" up 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}Interfaz encendida correctamente${NC}"
        else
            echo -e "${RED}Error al encender la interfaz. Verifica permisos.${NC}"
        fi
    fi
    read -p "Presiona ENTER para continuar..."
}
show_interface_config() {
    clear
    if [ -z "$SELECTED_INTERFACE" ]; then
        echo -e "${RED}Primero debes seleccionar una interfaz (Opción 2)${NC}"
        read -p "Presiona ENTER para continuar..."
        return 1
    fi
    echo -e "${BLUE}=== CONFIGURACIÓN FINAL DE LA INTERFAZ ===${NC}"
    echo ""
    echo -e "${GREEN}Nombre: ${NC}$SELECTED_INTERFACE"
    local state=$(ip -br addr show "$SELECTED_INTERFACE" 2>/dev/null | awk '{print $2}')
    echo -e "${GREEN}Estado: ${NC}$state"
    echo -e "${GREEN}Direcciones IP asignadas:${NC}"
    local ip_count=$(ip addr show "$SELECTED_INTERFACE" 2>/dev/null | grep -c 'inet ')
    if [ "$ip_count" -eq 0 ]; then
        echo "  Sin IPs asignadas"
    else
        ip addr show "$SELECTED_INTERFACE" 2>/dev/null | grep 'inet ' | awk '{print "  - " $2}'
    fi
    echo ""
    read -p "Presiona ENTER para continuar..."
}
show_menu() {
    clear
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  GESTOR DE INTERFACES DE RED LINUX    ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    echo ""
    if [ -n "$SELECTED_INTERFACE" ]; then
        echo -e "Interfaz seleccionada: ${GREEN}$SELECTED_INTERFACE${NC}"
        echo ""
    fi
    echo "1. Listar interfaces"
    echo "2. Seleccionar interfaz a configurar"
    echo "3. Limpiar IPs de la interfaz seleccionada"
    echo "4. Agregar o reemplazar IP en la interfaz"
    echo "5. Encender la interfaz si está apagada"
    echo "6. Mostrar configuración final de la interfaz"
    echo "7. Salir"
    echo ""
}
main() {
    if [ "$EUID" -ne 0 ] && ! sudo -n true 2>/dev/null; then
        echo -e "${YELLOW}⚠ Este script requiere permisos administrativos para algunas operaciones.${NC}"
        echo "Se te pedirá contraseña para los comandos que lo requieran."
        echo ""
    fi
    while true; do
        show_menu
        read -r -p "Elige una opción (1-7): " option
        option="${option// /}"
        option="${option
        option="${option%"${option
        case "$option" in
            1) list_interfaces ;;
            2) select_interface ;;
            3) flush_interface_ips ;;
            4) add_or_replace_ip ;;
            5) bring_up_interface ;;
            6) show_interface_config ;;
            7) 
                echo -e "${GREEN}¡Hasta luego!${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}Opción inválida: '$option'. Intenta nuevamente.${NC}"
                read -p "Presiona ENTER para continuar..."
                ;;
        esac
    done
}
main
