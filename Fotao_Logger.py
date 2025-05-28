import serial
import csv
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import os
import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import threading
import time
import sys

# Função para receber e traduzir os dados da conexão serial
def receive_and_parse_data(serial_port, baud_rate):
    """
    Lê uma linha da porta série, interpreta os dados no formato 'B:2.11 P:2.34',
    e retorna um dicionário com os valores de corrente das baterias e do painel solar.
    """
    try:
        line = serial_port.readline().decode('utf-8').strip()
        # Exemplo de linha: "B:2.11 P:2.34"
        if line:
            # Inicialização dos valores
            battery_current = None
            panel_current = None

            # Divide a linha em partes
            parts = line.split()
            for part in parts:
                if part.startswith("B:"):
                    try:
                        battery_current = float(part[2:])
                    except ValueError:
                        battery_current = None
                elif part.startswith("P:"):
                    try:
                        panel_current = float(part[2:])
                    except ValueError:
                        panel_current = None

            # Retorna apenas se ambos os valores estiverem presentes
            if battery_current is not None and panel_current is not None:
                # Adiciona timestamp para referência temporal
                return {
                    "timestamp": datetime.now(),
                    "battery_current": battery_current,
                    "panel_current": panel_current
                }
    except Exception as e:
        print(f"Erro ao ler/parsing dos dados da porta série: {e}")
    return None

# Função para analisar os dados recebidos
def analyze_data(parsed_data):
    """
    Recebe um dicionário com as correntes da bateria e do painel,
    calcula a diferença entre estes dois valores, e retorna os dados prontos para visualização.
    """
    if parsed_data is None:
        return None

    try:
        battery_current = parsed_data.get("battery_current")
        panel_current = parsed_data.get("panel_current")

        if battery_current is not None and panel_current is not None:
            current_difference = panel_current - battery_current
            # Estrutura de retorno pode ser expandida conforme necessário
            return {
                "timestamp": parsed_data.get("timestamp"),
                "battery_current": battery_current,
                "panel_current": panel_current,
                "current_difference": current_difference
            }
    except Exception as e:
        print(f"Erro ao analisar dados: {e}")
    return None

# Função para guardar os dados num ficheiro CSV ou Excel
def save_data_to_file(data, filename=None):

    """
    Guarda os dados analisados (dicionário) num ficheiro CSV.
    Se o ficheiro não existir, cria o cabeçalho.
    """
    # Gera nome único na primeira chamada e guarda como atributo da função
    if not hasattr(save_data_to_file, "unique_filename"):
        def generate_unique_filename(base="data_log", ext="csv"):
            idx = 1
            while True:
                fname = f"{base}_{idx}.{ext}"
                if not os.path.exists(fname):
                    return fname
                idx += 1
        save_data_to_file.unique_filename = filename or generate_unique_filename()
    filename = save_data_to_file.unique_filename

    if data is None:
        return

    fieldnames = ["timestamp", "battery_current", "panel_current", "current_difference"]
    if isinstance(data.get("timestamp"), float):
        data_to_write = data.copy()
        # Se quiseres converter float para string com mais casas decimais:
        data_to_write["timestamp"] = f"{data_to_write['timestamp']:.3f}"
    else:
        data_to_write = data.copy()

    file_exists = os.path.isfile(filename)

    try:
        with open(filename, 'a', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(data_to_write)
    except Exception as e:
        print(f"Erro ao guardar dados no ficheiro: {e}")


def visualize_data(data_list):
    # Função para obter o último dicionário de dados válido
    def get_last_data():
        for d in reversed(data_list):
            if d is not None and all(k in d for k in ("battery_current", "panel_current", "current_difference", "timestamp")):
                return d
        return None

    # Função para atualizar labels e LEDs
    def update_labels():
        last = get_last_data()
        if last is not None:
            batt_val.set(f"{last['battery_current']:.2f} A")
            panel_val.set(f"{last['panel_current']:.2f} A")
            diff_val.set(f"{last['current_difference']:.2f} A")

            diff = last['current_difference']
            # LED: verde se positiva (>1 ), vermelho se negativa (<-1), amarelo se perto de zero ([-1, 1])
            if diff > 1:
                led_canvas.itemconfig(green_led, fill="green")
                led_canvas.itemconfig(yellow_led, fill="grey")
                led_canvas.itemconfig(red_led, fill="grey")
            elif diff < -1:
                led_canvas.itemconfig(green_led, fill="grey")
                led_canvas.itemconfig(yellow_led, fill="grey")
                led_canvas.itemconfig(red_led, fill="red")
            else:
                led_canvas.itemconfig(green_led, fill="grey")
                led_canvas.itemconfig(yellow_led, fill="yellow")
                led_canvas.itemconfig(red_led, fill="grey")
        else:
            batt_val.set("--")
            panel_val.set("--")
            diff_val.set("--")
            led_canvas.itemconfig(green_led, fill="grey")
            led_canvas.itemconfig(yellow_led, fill="grey")
            led_canvas.itemconfig(red_led, fill="grey")
        root.after(500, update_labels)

    # Função para atualizar o gráfico
    def update_plot():
        window_size = 10  # segundos
        now = None
        times = []
        batt = []
        panel = []
        for d in data_list:
            if d is not None and all(k in d for k in ("timestamp", "battery_current", "panel_current")):
                times.append(d["timestamp"])
                batt.append(d["battery_current"])
                panel.append(d["panel_current"])
                now = d["timestamp"]  # último timestamp

        if now is not None and len(times) > 1:
            idx_start = 0
            for i, t in enumerate(times):
                if t >= now - window_size:
                    idx_start = i
                    break
            times = times[idx_start:]
            batt = batt[idx_start:]
            panel = panel[idx_start:]
        
        ax.clear()
        ax.plot(times, batt, label="Bateria [A]")
        ax.plot(times, panel, label="Painel [A]")
        
        # Adiciona linha tracejada de média, se houver dados
        if batt:
            mean = sum(batt) / len(batt)
            mean_line = [mean] * len(times)
            ax.plot(times, mean_line, label="Consumo médio", linestyle="--")

        ax.set_ylabel("Corrente (A)")
        ax.set_xlabel("Tempo")
        ax.legend(loc="upper left")
        fig.autofmt_xdate()
        ax.grid(True, which="both", linestyle="--", alpha=0.5)
        fig.tight_layout()
        canvas.draw()
        root.after(1000, update_plot)

    def on_closing():
        root.destroy()
        sys.exit(0)   # Garante que o processo termina
    

    # Interface Tkinter
    root = tk.Tk()
    root.title("Monitorização Correntes")

    # Labels dos valores
    large_font = ("Arial", 18, "bold")
    main_frame = ttk.Frame(root)
    main_frame.pack(padx=10, pady=10)
    ttk.Label(main_frame, text="Bateria:", font=large_font).grid(row=0, column=0)
    ttk.Label(main_frame, text="Painel:", font=large_font).grid(row=1, column=0)
    ttk.Label(main_frame, text="Diferença:", font=large_font).grid(row=2, column=0)

    batt_val = tk.StringVar(value="--")
    panel_val = tk.StringVar(value="--")
    diff_val = tk.StringVar(value="--")
    ttk.Label(main_frame, textvariable=batt_val, font=large_font).grid(row=0, column=1)
    ttk.Label(main_frame, textvariable=panel_val, font=large_font).grid(row=1, column=1)
    ttk.Label(main_frame, textvariable=diff_val, font=large_font).grid(row=2, column=1)

    # LEDs
    led_canvas = tk.Canvas(main_frame, width=200, height=70)
    led_canvas.grid(row=0, column=2, rowspan=3, padx=20)
    green_led = led_canvas.create_oval(20, 15, 60, 55, fill="grey")
    yellow_led = led_canvas.create_oval(80, 15, 120, 55, fill="grey")
    red_led = led_canvas.create_oval(140, 15, 180, 55, fill="grey")


    # Gráfico Matplotlib
    fig, ax = plt.subplots(figsize=(6, 3))
    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas.get_tk_widget().pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    # Iniciar atualizações
    root.after(500, update_labels)
    root.after(500, update_plot)
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
    

# Função principal que organiza a execução do script
def main():
    # Lista partilhada para armazenar os dados analisados
    parsed_data = []
    start_time = time.time()  # Guarda o tempo de arranque
    
    # Parâmetros default (ajustáveis conforme o teu setup)
    serial_port = 'COM6'      # Altera conforme o teu SO, ou deixa que o user selecione depois
    baud_rate = 9600

    # Inicia a comunicação serial
    try:
        ser = serial.Serial(serial_port, baud_rate, timeout=1)
        print(f"Connected to {serial_port} at {baud_rate} baud rate.")
    except serial.SerialException as e:
        print(f"Error connecting to serial port: {e}")
        return

    # Thread para leitura e processamento dos dados
    def serial_thread():
        while True:
            data = receive_and_parse_data(ser, baud_rate)
            analyzed = analyze_data(data)
            if analyzed:
                analyzed["timestamp"] = time.time() - start_time
                parsed_data.append(analyzed)
                save_data_to_file(analyzed)
            time.sleep(0.1)  # Reduz stress na porta e CPU

    # Lança a thread daemon para aquisição de dados
    thread = threading.Thread(target=serial_thread, daemon=True)
    thread.start()

    # Lança interface gráfica (blocking)
    visualize_data(parsed_data)

    # Após fechar a interface, encerra a porta série
    if ser.is_open:
        ser.close()


if __name__ == "__main__":
    main()
