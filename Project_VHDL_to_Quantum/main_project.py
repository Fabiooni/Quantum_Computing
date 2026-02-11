import re
import sys
import math
import os
import subprocess
import numpy as np
import matplotlib.pyplot as plt

from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import GroverOperator, Diagonal
from qiskit.visualization import plot_histogram
from qiskit_aer import AerSimulator

# Import IQM
from iqm.qiskit_iqm import IQMProvider
from iqm.qiskit_iqm import iqm_naive_move_pass

def authenticate_and_get_backend():
    """Gestisce login e connessione al Lagrange"""
    print("\n[Hardware] Controllo autenticazione...")
    # Lancia client per refresh token se necessario
    try:
        subprocess.run([sys.executable, "-m", "lagrangeclient"], check=True)
    except:
        print("Warning: Autenticazione automatica saltata o fallita.")

    os.environ["IQM_TOKENS_FILE"] = "./tokens.json"
    iqm_url = "https://spark.quantum.linksfoundation.com/station"
    
    print(f"[Hardware] Connessione a: {iqm_url}")
    provider = IQMProvider(iqm_url)
    backend = provider.get_backend()
    print(f"[Hardware] Connesso a: {backend.name}")
    return backend

def parse_vhdl_to_expression(filename):
    """Parser VHDL minimale"""
    with open(filename, 'r') as f:
        vhdl_code = f.read()
    match = re.search(r'(\w+)\s*<=\s*(.+?);', vhdl_code, re.DOTALL)
    if not match: raise ValueError("Nessuna assegnazione trovata.")
    expression = match.group(2).lower()
    expression = expression.replace('xor', '^') 
    
    variables = sorted(list(set(re.findall(r'\b[a-zA-Z]\w*\b', expression))))
    variables = [v for v in variables if v not in ['and', 'or', 'xor', 'not']]
    return expression, variables

def build_custom_oracle(expression, variables):
    """Costruisce Oracolo Diagonale"""
    num_vars = len(variables)
    num_states = 2**num_vars
    diagonal_elements = []
    solutions_count = 0
    
    for i in range(num_states):
        bin_str = format(i, f'0{num_vars}b')
        context = {var: (bin_str[idx] == '1') for idx, var in enumerate(variables)}
        try:
            if eval(expression, {}, context):
                diagonal_elements.append(-1)
                solutions_count += 1
            else:
                diagonal_elements.append(1)
        except: pass

    oracle_gate = Diagonal(diagonal_elements)
    oracle_gate.name = "VHDL_Oracle"
    return oracle_gate, num_vars, solutions_count

def main():
    vhdl_file = 'simple_circuit.vhd'
    
    try:
        # 1. Parsing & Costruzione Circuito
        print(f"--- FASE 1: Costruzione Circuito da {vhdl_file} ---")
        expr, vars_list = parse_vhdl_to_expression(vhdl_file)
        oracle, num_qubits, num_solutions = build_custom_oracle(expr, vars_list)
        
        if num_solutions == 0:
            print("Nessuna soluzione logica possibile.")
            return

        # Calcolo iterazioni
        N = 2**num_qubits
        M = num_solutions
        optimal_iterations = math.floor((math.pi / 4) * math.sqrt(N / M))
        if optimal_iterations < 1: optimal_iterations = 1
        
        print(f"Variabili: {vars_list} -> {num_qubits} Qubit")
        print(f"Soluzioni attese: {M}")
        print(f"Iterazioni Grover: {optimal_iterations}")

        # Circuito
        qc = QuantumCircuit(num_qubits)
        qc.h(range(num_qubits))
        grover_op = GroverOperator(oracle)
        for _ in range(optimal_iterations):
            qc.compose(grover_op, inplace=True)
        qc.measure_all()

        # ---------------------------------------------------------
        # FASE 2: SIMULATORE (Benchmark Ideale)
        # ---------------------------------------------------------
        print("\n--- FASE 2: Esecuzione su SIMULATORE (Ideale) ---")
        sim_backend = AerSimulator()
        # Transpile generico per simulatore
        qc_sim = transpile(qc, sim_backend)
        job_sim = sim_backend.run(qc_sim, shots=1024)
        counts_sim = job_sim.result().get_counts()
        
        # Ordina e stampa top solution
        sorted_sim = dict(sorted(counts_sim.items(), key=lambda x: x[1], reverse=True))
        best_sim = list(sorted_sim.keys())[0]
        print(f"Top Result Simulatore: {best_sim} ({sorted_sim[best_sim]} shots)")
        
        plot_histogram(counts_sim, title="Grover Simulation (Ideal)").savefig('grover_sim.png')

        # ---------------------------------------------------------
        # FASE 3: HARDWARE REALE (IQM Lagrange)
        # ---------------------------------------------------------
        print("\n--- FASE 3: Esecuzione su IQM LAGRANGE (Reale) ---")
        real_backend = authenticate_and_get_backend()
        
        print("Transpilazione per topologia Star (IQM)...")
        # Usiamo il transpiler IQM o quello standard con optimization 3
        # optimization_level=3 è cruciale per ridurre la profondità del circuito
        qc_real = transpile(qc, real_backend, optimization_level=3)
        
        depth = qc_real.depth()
        n_ops = qc_real.count_ops()
        print(f"Circuit Depth su Hardware: {depth}")
        print(f"Operazioni totali: {n_ops}")
        
        if depth > 50:
            print("ATTENZIONE: La profondità è elevata. Il rumore sarà significativo.")

        print("Invio job al QPU...")
        job_real = real_backend.run(qc_real, shots=1024)
        counts_real = job_real.result().get_counts()
        
        # ... (tutto il codice prima rimane uguale fino a counts_real) ...
        
        # Ordina risultati reali
        sorted_real = dict(sorted(counts_real.items(), key=lambda x: x[1], reverse=True))
        print(f"Risultati Hardware Grezzi: {sorted_real}")
        
        # --- MODIFICA GRAFICA ---
        print("\nGenerazione grafico migliorato...")
        
        # 1. Colori: Blu per Ideale, Violetto per Reale (Quantum Style)
        colors = ['#4da6ff', '#8A2BE2'] 
        
        # 2. Creazione Figura con dimensioni maggiori (12x7) per separare le colonne
        fig = plot_histogram(
            [counts_sim, counts_real], 
            legend=['Ideal (Sim)', 'Real (Lagrange)'], 
            title=f"Grover: Ideal vs Real (Depth: {depth})",
            color=colors,
            figsize=(12, 7) # Allarga l'immagine per dare aria alle colonne
        )

        # 3. Salvataggio con bbox_inches='tight' per NON tagliare le etichette
        # Salviamo in due formati per sicurezza
        save_path = 'grover_comparison_final.png'
        fig.savefig(save_path, bbox_inches='tight', dpi=300)
        
        print(f"Grafico salvato correttamente in alta risoluzione: {save_path}")

    except Exception as e:
        print(f"ERRORE: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
