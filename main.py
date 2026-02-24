from nicegui import ui
import json
import csv
import io
from datetime import datetime
import pandas as pd

# --- STAN APLIKACJI ---
class AppState:
    def __init__(self):
        self.variants = []
        self.criteria = []
        self.matrix = []
        self.p = 0.6
        self.q = 0.4
        self.results = None

    def clear(self):
        self.__init__()

state = AppState()

# --- LOGIKA ALGORYTMU MAJA ---
def run_maja():
    if len(state.variants) < 2:
        ui.notify('Musisz mieć co najmniej 2 warianty', type='warning')
        return
    if len(state.criteria) == 0:
        ui.notify('Musisz mieć co najmniej 1 kryterium', type='warning')
        return
    if len(state.matrix) == 0 or len(state.matrix[0]) == 0:
        ui.notify('Wypełnij macierz ocen', type='warning')
        return

    # Normalizacja
    n_vars = len(state.variants)
    n_crit = len(state.criteria)
    normalized = [[0.0] * n_crit for _ in range(n_vars)]
    
    for j, c in enumerate(state.criteria):
        col = [state.matrix[i][j] for i in range(n_vars)]
        max_val, min_val = max(col), min(col)
        val_range = max_val - min_val
        
        for i in range(n_vars):
            if val_range == 0:
                normalized[i][j] = 0.5
            elif c['type'] == 'max':
                normalized[i][j] = (state.matrix[i][j] - min_val) / val_range
            else:
                normalized[i][j] = (max_val - state.matrix[i][j]) / val_range

    # Macierz zgodności (Concordance)
    concordance = [[0.0] * n_vars for _ in range(n_vars)]
    weights = [c['weight'] for c in state.criteria]
    total_weight = sum(weights)

    for i in range(n_vars):
        for j in range(n_vars):
            if i == j:
                concordance[i][j] = 1.0
            else:
                s = sum(weights[k] for k in range(n_crit) if normalized[i][k] >= normalized[j][k])
                concordance[i][j] = s / total_weight if total_weight > 0 else 0

    # Macierz niezgodności (Discordance)
    discordance = [[0.0] * n_vars for _ in range(n_vars)]
    for i in range(n_vars):
        for j in range(n_vars):
            if i == j:
                discordance[i][j] = 0.0
            else:
                max_diff = 0.0
                for k in range(n_crit):
                    diff = max(0.0, normalized[j][k] - normalized[i][k])
                    max_diff = max(max_diff, diff)
                discordance[i][j] = max_diff

    # Dominacja
    dominance = [[False] * n_vars for _ in range(n_vars)]
    for i in range(n_vars):
        for j in range(n_vars):
            if i != j and concordance[i][j] >= state.p and discordance[i][j] <= state.q:
                dominance[i][j] = True

    # Ranking
    dominated = [0] * n_vars
    dominates = [0] * n_vars
    for i in range(n_vars):
        for j in range(n_vars):
            if dominance[i][j]: dominates[i] += 1
            if dominance[j][i]: dominated[i] += 1

    scores = []
    for i in range(n_vars):
        scores.append({
            'index': i,
            'score': dominates[i] - dominated[i],
            'dominates': dominates[i],
            'dominated': dominated[i]
        })
    scores.sort(key=lambda x: x['score'], reverse=True)

    state.results = {
        'normalized': normalized,
        'concordance': concordance,
        'discordance': discordance,
        'dominance': dominance,
        'ranking': scores,
        'p': state.p,
        'q': state.q
    }
    
    results_ui.refresh()
    ui.notify('Analiza MAJA zakończona pomyślnie!', type='positive')

# --- IMPORT / EKSPORT ---
def handle_upload(e):
    try:
        content = e.content.read()
        filename = e.name
        
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content))
        elif filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(io.BytesIO(content))
        else:
            ui.notify('Nieobsługiwany format. Użyj pliku .csv lub .xlsx', type='negative')
            return

        # Walidacja struktury
        if len(df) < 3:
            ui.notify('Plik jest za krótki. Brakuje wierszy z wagami, typami lub wariantami.', type='warning')
            return

        # Odczyt kryteriów (pomijamy pierwszą kolumnę "Wariant")
        criteria_names = df.columns[1:].tolist()
        weights_row = df.iloc[0, 1:].tolist()
        types_row = df.iloc[1, 1:].tolist()
        
        state.criteria = []
        for name, w, t in zip(criteria_names, weights_row, types_row):
            state.criteria.append({
                'name': str(name),
                'weight': float(w),
                'type': str(t).strip().lower() # oczekiwane 'max' lub 'min'
            })
            
        # Odczyt wariantów i macierzy (od 3 wiersza w dół)
        state.variants = df.iloc[2:, 0].astype(str).tolist()
        matrix_data = df.iloc[2:, 1:].values.tolist()
        state.matrix = [[float(val) for val in row] for row in matrix_data]
        
        update_all_ui()
        ui.notify(f'Pomyślnie wczytano dane z pliku: {filename}', type='positive')
        
    except Exception as ex:
        ui.notify(f'Błąd podczas wczytywania pliku: {str(ex)}', type='negative')

def download_template():
    csv_content = "Wariant,Kryterium 1,Kryterium 2,Kryterium 3\n"
    csv_content += "WAGI,0.4,0.3,0.3\n"
    csv_content += "TYPY,max,min,max\n"
    csv_content += "Opcja A,100,50,4.5\n"
    csv_content += "Opcja B,120,60,4.0\n"
    csv_content += "Opcja C,90,40,4.8\n"
    ui.download(csv_content.encode('utf-8'), 'szablon_maja.csv')

def export_json():
    data = {
        "variants": state.variants,
        "criteria": state.criteria,
        "matrix": state.matrix,
        "results": state.results,
        "timestamp": datetime.now().isoformat()
    }
    ui.download(json.dumps(data, indent=2).encode('utf-8'), 'maja-analysis.json')

def export_csv():
    csv_str = "Wariant," + ",".join([c['name'] for c in state.criteria]) + "\n"
    for i, v in enumerate(state.variants):
        csv_str += f"{v}," + ",".join([str(val) for val in state.matrix[i]]) + "\n"
    
    csv_str += "\nRanking\nMiejsce,Wariant,Wynik,Dominuje,Dominowany\n"
    for idx, item in enumerate(state.results['ranking']):
        csv_str += f"{idx+1},{state.variants[item['index']]},{item['score']},{item['dominates']},{item['dominated']}\n"
    
    ui.download(csv_str.encode('utf-8'), 'maja-analysis.csv')

def load_example():
    state.variants = ['Lenovo X1 Carbon G5', 'Lenovo P1 Gen 2', 'Lenovo P50', 'Lenovo T480s']
    state.criteria = [
        {'name': 'Procesor (rdzenie)', 'type': 'max', 'weight': 0.15},
        {'name': 'RAM (GB)', 'type': 'max', 'weight': 0.15},
        {'name': 'Dysk (GB)', 'type': 'max', 'weight': 0.10},
        {'name': 'Matryca (cale)', 'type': 'max', 'weight': 0.10},
        {'name': 'Waga (kg)', 'type': 'min', 'weight': 0.10},
        {'name': 'Złącza (ilość)', 'type': 'max', 'weight': 0.10},
        {'name': 'Generacja', 'type': 'max', 'weight': 0.15},
        {'name': 'Cena (zł)', 'type': 'min', 'weight': 0.15}
    ]
    state.matrix = [
        [2, 16, 256, 14, 1.13, 5, 7, 3779],
        [6, 32, 1000, 15.6, 1.8, 6, 9, 6601],
        [4, 64, 1024, 15.6, 2.7, 8, 6, 4679],
        [4, 16, 512, 14, 1.31, 7, 8, 3889]
    ]
    state.p, state.q = 0.6, 0.4
    update_all_ui()
    ui.notify('Załadowano przykład. Kliknij "Uruchom analizę MAJA"', type='info')

def update_all_ui():
    variants_ui.refresh()
    criteria_ui.refresh()
    matrix_ui.refresh()
    results_ui.refresh()

# --- KOMPONENTY INTERFEJSU (UI) ---
@ui.refreshable
def variants_ui():
    with ui.column().classes('w-full gap-2 mt-4'):
        if not state.variants:
            ui.label('Brak wariantów').classes('text-gray-500 italic text-sm')
        for i, v in enumerate(state.variants):
            with ui.row().classes('w-full items-center justify-between p-2 bg-blue-50 border-l-4 border-blue-500 rounded'):
                ui.label(v).classes('font-medium')
                def remove_v(idx=i):
                    state.variants.pop(idx)
                    state.matrix.pop(idx)
                    update_all_ui()
                ui.button('✕', on_click=remove_v).props('flat color=red size=sm')

@ui.refreshable
def criteria_ui():
    with ui.column().classes('w-full gap-2 mt-4'):
        if not state.criteria:
            ui.label('Brak kryteriów').classes('text-gray-500 italic text-sm')
        for i, c in enumerate(state.criteria):
            icon = '📈' if c['type'] == 'max' else '📉'
            with ui.row().classes('w-full items-center justify-between p-2 bg-blue-50 border-l-4 border-blue-500 rounded'):
                with ui.column().classes('gap-0'):
                    ui.label(c['name']).classes('font-medium')
                    ui.label(f"{icon} • Waga: {c['weight']}").classes('text-xs text-gray-500')
                def remove_c(idx=i):
                    state.criteria.pop(idx)
                    for row in state.matrix:
                        row.pop(idx)
                    update_all_ui()
                ui.button('✕', on_click=remove_c).props('flat color=red size=sm')

@ui.refreshable
def matrix_ui():
    if not state.variants or not state.criteria:
        ui.label('Dodaj warianty i kryteria aby zobaczyć macierz').classes('text-gray-500')
        return
    
    with ui.grid(columns=len(state.criteria) + 1).classes('w-full items-center gap-2 overflow-x-auto'):
        ui.label('Wariant / Kryterium').classes('font-bold bg-blue-500 text-white p-2 rounded')
        for c in state.criteria:
            ui.label(c['name']).classes('font-bold bg-blue-500 text-white p-2 rounded text-center')
        
        for i, v in enumerate(state.variants):
            ui.label(v).classes('font-bold p-2 bg-gray-100 rounded')
            for j, c in enumerate(state.criteria):
                def update_val(e, r=i, col=j):
                    state.matrix[r][col] = float(e.value) if e.value else 0.0
                ui.number(value=state.matrix[i][j], on_change=update_val, format='%.2f').classes('w-full')

@ui.refreshable
def results_ui():
    if not state.results:
        return
    
    res = state.results
    ui.separator().classes('my-8')
    ui.label('🏆 Wyniki Analizy MAJA').classes('text-2xl font-bold text-blue-600 mb-4')
    
    with ui.column().classes('w-full gap-2 mb-6'):
        for idx, item in enumerate(res['ranking']):
            v_name = state.variants[item['index']]
            medal = '🥇' if idx == 0 else '🥈' if idx == 1 else '🥉' if idx == 2 else f'{idx+1}.'
            color = 'bg-yellow-400' if idx == 0 else 'bg-gray-400' if idx == 1 else 'bg-amber-600' if idx == 2 else 'bg-blue-500'
            
            with ui.row().classes('w-full items-center p-4 bg-white shadow rounded border-l-4 border-blue-500 gap-4'):
                ui.label(medal).classes(f'text-white text-xl font-bold w-12 h-12 flex items-center justify-center rounded-full {color}')
                with ui.column().classes('gap-0'):
                    ui.label(v_name).classes('text-lg font-bold')
                    ui.label(f"Wynik: {item['score']:.2f} | Dominuje: {item['dominates']} | Dominowany: {item['dominated']}").classes('text-sm text-gray-600')

    def matrix_table(matrix_data):
        cols = [{'name': 'var', 'label': 'i \\ j', 'field': 'var', 'align': 'left'}]
        for j, v in enumerate(state.variants):
            cols.append({'name': str(j), 'label': v, 'field': str(j)})
        
        rows = []
        for i, row in enumerate(matrix_data):
            row_dict = {'var': state.variants[i]}
            for j, val in enumerate(row):
                row_dict[str(j)] = f"{val:.3f}"
            rows.append(row_dict)
        ui.table(columns=cols, rows=rows, row_key='var').classes('w-full')

    with ui.expansion('📊 Macierz Zgodności (C[i,j])', icon='analytics').classes('w-full bg-white shadow mb-2'):
        matrix_table(res['concordance'])

    with ui.expansion('📉 Macierz Niezgodności (D[i,j])', icon='trending_down').classes('w-full bg-white shadow mb-2'):
        matrix_table(res['discordance'])

    with ui.expansion('📈 Macierz Znormalizowana', icon='transform').classes('w-full bg-white shadow mb-2'):
        cols = [{'name': 'var', 'label': 'Wariant', 'field': 'var', 'align': 'left'}]
        for j, c in enumerate(state.criteria):
            cols.append({'name': str(j), 'label': c['name'], 'field': str(j)})
        
        rows = []
        for i, row in enumerate(res['normalized']):
            row_dict = {'var': state.variants[i]}
            for j, val in enumerate(row):
                row_dict[str(j)] = f"{val:.3f}"
            rows.append(row_dict)
        ui.table(columns=cols, rows=rows, row_key='var').classes('w-full')

    with ui.row().classes('gap-4 mt-6'):
        ui.button('💾 Pobierz JSON', on_click=export_json, color='green')
        ui.button('📋 Pobierz CSV (Wyniki)', on_click=export_csv, color='green')

# --- BUDOWA GŁÓWNEGO OKNA ---
ui.page_title('MAJA - Metoda Oceny Wielokryterialnej')
ui.add_head_html('<style>body { background-color: #f8fafc; }</style>')

with ui.column().classes('w-full max-w-screen-xl mx-auto p-4 gap-6'):
    with ui.column().classes('w-full bg-gradient-to-r from-blue-600 to-blue-800 text-white p-8 rounded-xl shadow'):
        ui.label('🎯 MAJA - Metoda Oceny Wielokryterialnej').classes('text-3xl font-bold mb-2')
        ui.label('Analiza decyzyjna wielokryterialna oparta na wskaźnikach zgodności i niezgodności').classes('text-lg opacity-90')
    
    # Przycisk "Załaduj przykład" i sekcja Importu
    with ui.row().classes('w-full justify-between items-center bg-white p-4 rounded shadow border'):
        ui.button('🎓 Załaduj zdefiniowany przykład', on_click=load_example, color='blue', icon='school')
        
        with ui.row().classes('items-center gap-4'):
            ui.button('📄 Pobierz szablon CSV', on_click=download_template, color='gray').props('outline')
            ui.upload(on_upload=handle_upload, label='Wczytaj CSV / Excel', auto_upload=True).classes('w-64')

    with ui.row().classes('w-full gap-6'):
        with ui.column().classes('flex-1 min-w-[300px] gap-6'):
            with ui.card().classes('w-full'):
                ui.label('📊 Warianty').classes('text-xl font-bold text-blue-600')
                v_input = ui.input('Nazwa wariantu').classes('w-full')
                def add_v():
                    name = v_input.value.strip()
                    if name and name not in state.variants:
                        state.variants.append(name)
                        state.matrix.append([0.0] * len(state.criteria))
                        v_input.value = ''
                        update_all_ui()
                ui.button('➕ Dodaj wariant', on_click=add_v).classes('w-full mt-2')
                variants_ui()

            with ui.card().classes('w-full'):
                ui.label('📋 Kryteria').classes('text-xl font-bold text-blue-600')
                c_input = ui.input('Nazwa kryterium').classes('w-full')
                c_type = ui.select({'max': 'Maksymalizacja (wyżej lepiej)', 'min': 'Minimalizacja (niżej lepiej)'}, value='max', label='Typ').classes('w-full mt-2')
                c_weight = ui.number('Waga (0-1)', value=0.1, min=0, max=1, step=0.01).classes('w-full mt-2')
                def add_c():
                    name = c_input.value.strip()
                    if name and c_weight.value is not None:
                        state.criteria.append({'name': name, 'type': c_type.value, 'weight': c_weight.value})
                        for row in state.matrix:
                            row.append(0.0)
                        c_input.value = ''
                        update_all_ui()
                ui.button('➕ Dodaj kryterium', on_click=add_c).classes('w-full mt-2')
                criteria_ui()

            with ui.card().classes('w-full'):
                ui.label('⚙️ Parametry MAJA').classes('text-xl font-bold text-blue-600')
                def update_p(e): state.p = e.value
                def update_q(e): state.q = e.value
                ui.number('Próg zgodności (p, 0-1)', value=state.p, on_change=update_p, step=0.01).classes('w-full')
                ui.number('Próg niezgodności (q, 0-1)', value=state.q, on_change=update_q, step=0.01).classes('w-full')

        with ui.column().classes('flex-[2] min-w-[300px] gap-6'):
            with ui.card().classes('w-full'):
                ui.label('📈 Macierz Ocen').classes('text-xl font-bold text-blue-600 mb-4')
                matrix_ui()
                
                with ui.row().classes('gap-4 mt-6'):
                    ui.button('🚀 Uruchom analizę MAJA', on_click=run_maja, color='blue').classes('px-6')
                    def clear_all():
                        state.clear()
                        update_all_ui()
                    ui.button('🔄 Wyczyść wszystko', on_click=clear_all, color='red').props('outline')

    results_ui()

ui.run(host='0.0.0.0', port=8080, title='MAJA', favicon='🎯')