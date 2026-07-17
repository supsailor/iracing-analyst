import React,{useEffect,useMemo,useState} from 'react'
import{createRoot}from'react-dom/client'
import{useTranslation}from'react-i18next'
import{Line,LineChart,ResponsiveContainer,Tooltip,XAxis,YAxis}from'recharts'
import'./i18n'
import'./styles.css'
import type{Report,Series,Session}from'./types'

const fmt=(v:number|null)=>v==null?'—':`${Math.floor(v/60)}:${(v%60).toFixed(3).padStart(6,'0')}`
async function json<T>(url:string,init?:RequestInit):Promise<T>{const r=await fetch(url,init);if(!r.ok)throw new Error(await r.text());return r.json()}

function App(){
 const{t,i18n}=useTranslation();const[sessions,setSessions]=useState<Session[]>([]);const[report,setReport]=useState<Report|null>(null);const[series,setSeries]=useState<Series|null>(null);const[health,setHealth]=useState({simulator_connected:false,recording:false});const[busy,setBusy]=useState(false);const[error,setError]=useState('')
 const reload=()=>json<Session[]>('/api/sessions').then(setSessions)
 useEffect(()=>{reload();const timer=setInterval(()=>{json<typeof health>('/api/health').then(setHealth);reload()},3000);return()=>clearInterval(timer)},[])
 const open=async(id:string)=>{const next=await json<Report>(`/api/sessions/${id}`);setReport(next);if(next.best_lap&&next.median_lap)setSeries(await json<Series>(`/api/sessions/${id}/telemetry?selected_lap=${next.best_lap}&reference_lap=${next.median_lap}`))}
 const upload=async(e:React.ChangeEvent<HTMLInputElement>)=>{const file=e.target.files?.[0];if(!file)return;setBusy(true);setError('');const body=new FormData();body.append('file',file);try{const r=await json<Report>('/api/import',{method:'POST',body});await reload();await open(r.session_id)}catch(x){setError(String(x))}finally{setBusy(false);e.target.value=''}}
 const chart=useMemo(()=>series?.distance_pct.map((x,i)=>({x:x*100,speed:(series.selected.speed[i]||0)*3.6,refSpeed:(series.reference.speed[i]||0)*3.6,throttle:(series.selected.throttle[i]||0)*100,refThrottle:(series.reference.throttle[i]||0)*100,brake:(series.selected.brake[i]||0)*100,refBrake:(series.reference.brake[i]||0)*100,steering:series.selected.steering[i]||0,refSteering:series.reference.steering[i]||0,delta:series.selected.delta[i]||0})),[series])
 const language=i18n.language.startsWith('ru')?'ru':'en'
 const swap=()=>{const next=language==='ru'?'en':'ru';localStorage.setItem('language',next);i18n.changeLanguage(next)}
 return <div className="app"><header><div><span className="mark">IA</span><h1>{t('title')}</h1></div><div className="status"><span className={health.recording?'dot live':'dot'}/>{health.recording?t('recording'):t('waiting')}<button onClick={swap}>{language.toUpperCase()}</button></div></header>
 <div className="layout"><aside><h2>{t('sessions')}</h2><label className="upload">{busy?'…':t('import')}<input type="file" accept=".ibt,.npz" onChange={upload}/></label>{error&&<p className="error">{error}</p>}<div className="sessionList">{sessions.map(s=><button key={s.id} className={report?.session_id===s.id?'active':''} onClick={()=>open(s.id)}><strong>{s.track}</strong><span>{s.car}</span><small>{new Date(s.created_at).toLocaleString()} · {fmt(s.best_time)}</small></button>)}</div></aside>
 <main>{!report?<div className="empty"><div className="track">⌁</div><p>{t('noSession')}</p></div>:<><section className="hero"><div><p className="eyebrow">{report.car}</p><h2>{report.track}</h2><span>{report.laps.length} laps · {(report.confidence*100).toFixed(0)}% {t('confidence').toLowerCase()}</span></div><div className="cards"><Metric label={t('best')} value={fmt(report.best_time)}/><Metric label={t('median')} value={fmt(report.median_time)}/><Metric label={t('optimal')} value={fmt(report.sector_optimal)}/><Metric accent label={t('potential')} value={report.potential_gap==null?'—':`-${report.potential_gap.toFixed(3)}s`}/></div></section>
 <section className="panel"><h3>{t('corners')}</h3><div className="segments">{report.segments.map(s=><article key={s.id}><div><b>{s.name}</b><span className="gain">-{s.delta_to_best.toFixed(3)}s</span></div><div className="bar"><i style={{width:`${Math.min(100,s.confidence*100)}%`}}/></div><small>{t('sourceLap')} {s.source_lap} · {Math.round(s.minimum_speed_kph)} km/h min</small></article>)}</div></section>
 {chart&&<section className="panel"><h3>{t('selected')} vs {t('reference')}</h3>{(['speed','throttle','brake','steering','delta'] as const).map(key=><Chart key={key} data={chart} field={key} reference={'ref'+key[0].toUpperCase()+key.slice(1)} title={t(key)}/>)}</section>}
 <section className="panel"><h3>{t('recommendations')}</h3><div className="recommendations">{report.recommendations.map((r,i)=><article key={r.segment_id}><em>0{i+1}</em><div><h4>{r.segment_id.replace('segment-','T')} · {t(r.title_key)}</h4><p>{t(r.message_key)}</p><small>{t('loss')}: {r.expected_gain.toFixed(3)}s · {t('confidence')}: {(r.confidence*100).toFixed(0)}%</small></div></article>)}</div></section></>}</main></div></div>
}
function Metric({label,value,accent=false}:{label:string,value:string,accent?:boolean}){return <div className={accent?'metric accent':'metric'}><span>{label}</span><strong>{value}</strong></div>}
function Chart({data,field,reference,title}:{data:any[];field:string;reference:string;title:string}){return <div className="chart"><span>{title}</span><ResponsiveContainer width="100%" height={105}><LineChart data={data}><XAxis dataKey="x" hide/><YAxis width={42} tick={{fontSize:10}} domain={['auto','auto']}/><Tooltip labelFormatter={v=>`${Number(v).toFixed(1)}%`}/><Line dataKey={reference} stroke="#627087" dot={false} strokeWidth={1}/><Line dataKey={field} stroke="#e8ff47" dot={false} strokeWidth={2}/></LineChart></ResponsiveContainer></div>}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)

