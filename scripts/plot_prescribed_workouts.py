"""Plot every exported workout and its inferred prescription, without signal edits.

Run: .venv/Scripts/python -B scripts/plot_prescribed_workouts.py --output reports/prescribed_workouts_final_plots
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.mplconfig'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

BLUE = '#26769A'
ORANGE = '#D45A20'
PURPLE = '#8B5CAB'
DARK = '#203548'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def broken_line(time, values, segment_ids=None):
    """Break on recording gaps/non-increasing time; never smooth or decimate."""
    boundary=(np.diff(time) != 1)
    if segment_ids is not None:
        boundary|=np.diff(segment_ids)!=0
        values=np.where(segment_ids>0,values,np.nan)
    breaks = np.flatnonzero(boundary) + 1
    return np.insert(time / 60, breaks, np.nan), np.insert(values, breaks, np.nan)


def spans(frame, kind):
    time = frame.elapsed_seconds.to_numpy(float)
    mask = frame.prescription_kind.eq(kind).to_numpy(copy=True)
    boundary=np.diff(time)!=1
    if 'power_segment_id' in frame:
        mask&=frame.power_segment_id.to_numpy()>0
        boundary|=np.diff(frame.power_segment_id.to_numpy())!=0
    starts = np.flatnonzero(mask & np.r_[True, ~mask[:-1] | boundary])
    ends = np.flatnonzero(mask & np.r_[~mask[1:] | boundary, True])
    for first, last in zip(starts, ends):
        end = time[last] + 1
        if last + 1 < len(time) and time[last+1] - time[last] == 1:
            end = time[last+1]
        yield time[first] / 60, end / 60


def paint(ax, frame, measured=True, prescribed=True):
    time = frame.elapsed_seconds.to_numpy(float)
    ids=frame.power_segment_id.to_numpy() if 'power_segment_id' in frame else None
    if measured:
        x, y = broken_line(time, frame.power_w.to_numpy(float),ids)
        ax.plot(x, y, color=BLUE, lw=.75, alpha=.85, rasterized=True)
    if prescribed:
        x, y = broken_line(time, frame.power_target_w.to_numpy(float),ids)
        ax.step(x, y, where='post', color=ORANGE, lw=1.7)
    for start, end in spans(frame, 'maximal'):
        ax.axvspan(start, end, color=PURPLE, alpha=.20, lw=0)
    ax.set_ylabel('Potenza [W]')
    ax.set_xlabel('Tempo trascorso [min]')
    ax.grid(axis='y', color='#D9E2E9', lw=.65)
    ax.set_axisbelow(True)
    ax.set_ylim(bottom=0)


def detail_window(workout, frame):
    time = frame.elapsed_seconds.to_numpy(float)
    steps = {row['lap_index']: row for row in workout['steps']}
    if workout['blocks']:
        block = max(workout['blocks'], key=lambda b: len(b['lap_indices']))
        members = block['lap_indices'][:8]
        start = steps[members[0]]['start_elapsed_s']
        end = steps[members[-1]]['end_elapsed_s'] + 1
        padding = max(15, min(60, (end-start)*.06))
        label = f"Dettaglio blocco {block['block_id']} - prime {len(members)} fasi"
        return max(0,start-padding), min(time[-1],end+padding), label
    target = frame.power_target_w.to_numpy(float)
    changes = np.abs(np.diff(target))
    center = time[int(np.nanargmax(changes))+1] if np.isfinite(changes).any() and np.nanmax(changes)>0 else time[-1]/2
    start = max(0, min(center-300, time[-1]-600))
    return start, min(time[-1],start+600), 'Dettaglio della transizione principale (fino a 10 min)'


def make_figure(workout, frame, index, total):
    segmented='hr_segment_id' in frame
    fig, axes = plt.subplots(4 if segmented else 3, 1, figsize=(15,12 if segmented else 10),
                             gridspec_kw={'height_ratios':[1.15,1,.85,1.25] if segmented else [1.15,1,1.25]})
    fig.subplots_adjust(left=.065, right=.98, bottom=.10, top=.84, hspace=.52)
    identifier = workout['workout_id']
    date = pd.to_datetime(frame.timestamp.dropna().iloc[0], utc=True).strftime('%d/%m/%Y')
    duration = frame.elapsed_seconds.max()/60
    maximal = sum(row['prescription_kind']=='maximal' for row in workout['steps'])
    fig.text(.065,.956,f'{date}  /  {identifier}', fontsize=22, weight='bold', color=DARK)
    fig.text(.065,.920,f'{duration:.1f} min  |  {workout["lap_count"]} lap  |  {len(workout["blocks"])} blocchi candidati  |  {maximal} lap massimali  |  FTP 325 W',
             fontsize=11, color='#526574')
    fig.text(.98,.956,f'{index:02d} / {total}', ha='right', fontsize=12, color='#526574')
    fig.legend(handles=[Line2D([],[],color=BLUE,lw=1.5,label='Potenza misurata'),
                        Line2D([],[],color=ORANGE,lw=2,label='Prescrizione numerica'),
                        Patch(facecolor=PURPLE,alpha=.25,label='Massimale (categorico, nessun target in W)')],
               loc='upper left',bbox_to_anchor=(.057,.9),ncol=3,frameon=False,fontsize=10)
    paint(axes[0],frame,measured=True,prescribed=False)
    axes[0].set_title('01  Esecuzione reale - sessione completa',loc='left',fontsize=12,weight='bold',color=DARK)
    paint(axes[1],frame,measured=False,prescribed=True)
    axes[1].set_title('02  Allenamento prescritto inferito - tempi dei lap osservati',loc='left',fontsize=12,weight='bold',color=DARK)
    numeric = frame.power_target_w.dropna()
    axes[1].set_ylim(0,max(400,float(numeric.max())*1.13 if len(numeric) else 400))
    for ax in axes[:2]:
        ax.set_xlim(0,max(1,duration))
    if segmented:
        x,y=broken_line(frame.elapsed_seconds.to_numpy(float),frame.heart_rate_bpm.to_numpy(float),frame.hr_segment_id.to_numpy())
        axes[2].plot(x,y,color='#43734D',lw=.85,rasterized=True)
        axes[2].set_title('03  Frequenza cardiaca misurata - nessun collegamento attraverso i buchi',loc='left',fontsize=12,weight='bold',color=DARK)
        axes[2].set_ylabel('HR [bpm]');axes[2].set_xlabel('Tempo trascorso [min]')
        axes[2].set_xlim(0,max(1,duration));axes[2].grid(axis='y',alpha=.25)
    start,end,label = detail_window(workout,frame)
    detail=frame[(frame.elapsed_seconds>=start)&(frame.elapsed_seconds<=end)]
    paint(axes[-1],detail)
    axes[-1].set_xlim(start/60,max((start+1)/60,end/60))
    axes[-1].set_title(f'{"04" if segmented else "03"}  {label} - misurata e prescritta',loc='left',fontsize=12,weight='bold',color=DARK)
    fig.text(.065,.047,'Campioni originali, senza filtro o ricampionamento. Linee interrotte sui buchi e sui confini dei segmenti. Scale verticali adattate ai pannelli.',
             fontsize=9,color='#526574')
    fig.text(.065,.027,'Prescrizione inferita a posteriori; tempi non riscalati. Fasce viola: media lap >488 W, convenzione del dataset; altezza della fascia non numerica.',
             fontsize=9,color='#526574')
    return fig, {'detail_start_s':start,'detail_end_s':end,'detail_rule':label}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=ROOT/'data/processed/prescribed_workouts_final')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    source=args.input.resolve(); output=args.output.resolve()
    if output==source or output.is_relative_to(source):
        raise ValueError('Plots must be outside the immutable dataset')
    manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    for name in ['workouts.jsonl']:
        if sha(source/name)!=manifest['output_sha256'][name]: raise ValueError(f'Hash mismatch: {name}')
    workouts=[json.loads(line) for line in (source/'workouts.jsonl').read_text(encoding='utf-8').splitlines()]
    if len(workouts)!=manifest['summary']['exported_workouts']:
        raise ValueError('Workout count does not match manifest')
    output.mkdir(parents=True,exist_ok=False)
    (output/'png').mkdir()
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                         'axes.spines.right':False,'axes.edgecolor':'#B2C0CD',
                         'figure.facecolor':'white','savefig.facecolor':'white','path.simplify':False})
    entries=[]
    pdf_path=output/'allenamenti_reali_e_prescritti.pdf'
    with PdfPages(pdf_path,metadata={'Title':f'{len(workouts)} allenamenti - potenza reale e prescrizione inferita',
                                    'Author':'power_HR_model','Subject':f"{manifest['rules']['version']}, FTP 325 W"}) as pdf:
        for index,workout in enumerate(workouts,1):
            path=source/workout['sample_file']
            if sha(path)!=manifest['output_sha256'][workout['sample_file']]:
                raise ValueError(f'Sample hash mismatch: {path}')
            frame=pd.read_csv(path)
            figure,detail=make_figure(workout,frame,index,len(workouts))
            name=f"png/{index:02d}_{workout['workout_id']}.png"
            figure.savefig(output/name,dpi=160)
            pdf.savefig(figure,dpi=180)
            plt.close(figure)
            entries.append({'workout_id':workout['workout_id'],'page':index,'png':name,
                            'samples_plotted':len(frame),'source_samples_sha256':sha(path),**detail})
            print(f'{index}/{len(workouts)} {workout["workout_id"]}',flush=True)
    plot_manifest={'source_dataset':str(source),'source_manifest_sha256':sha(source/'manifest.json'),
                   'script_sha256':sha(__file__),'pdf':pdf_path.name,'workouts':entries,
                   'preprocessing':{'filtering':False,'resampling':False,'time_warping':False,
                                    'visual_line_break_gap_s':1,'segment_boundaries_respected':True,
                                    'maximal_representation':'categorical shaded spans'},
                   'output_sha256':{p.relative_to(output).as_posix():sha(p) for p in sorted(output.rglob('*')) if p.is_file()}}
    (output/'manifest.json').write_text(json.dumps(plot_manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
