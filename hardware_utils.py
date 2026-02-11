def extraer_gen(proc):
    if not proc or str(proc).strip().lower() in ['n/a', '', 'nan']:
        return 'moderno'

    p = str(proc).lower()

    obsoletos = ['4th','5th','6th','7th','8th','9th','4ta','5ta','6ta','7ta','8va','9na','gen 8','gen 9']
    if any(x in p for x in obsoletos):
        return 'obsoleto'

    modernos = ['10th','11th','12th','13th','14th','10ma','11va','12va','13va','14va','gen 10','gen 11','gen 12']
    if any(x in p for x in modernos):
        return 'moderno'

    return 'moderno'
