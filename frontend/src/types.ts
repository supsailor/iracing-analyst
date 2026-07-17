export type Session = {id:string;created_at:string;track:string;car:string;source:string;laps:number;best_time:number|null;status:string}
export type Lap = {number:number;time:number;valid:boolean;representative:boolean;reason:string|null}
export type Segment = {id:string;name:string;start_pct:number;end_pct:number;confidence:number;best_time:number;median_time:number;selected_time:number;delta_to_best:number;stability:number;source_lap:number;entry_speed_kph:number;minimum_speed_kph:number;exit_speed_kph:number;steering_corrections:number}
export type Recommendation = {rule:string;segment_id:string;title_key:string;message_key:string;confidence:number;expected_gain:number;evidence:{metric:string;value:number;unit:string}[]}
export type Report = {session_id:string;track:string;car:string;created_at:string;sample_count:number;laps:Lap[];best_lap:number|null;best_time:number|null;median_lap:number|null;median_time:number|null;sector_optimal:number|null;potential_gap:number|null;segments:Segment[];recommendations:Recommendation[];confidence:number}
export type Series = {distance_pct:number[];selected:Record<string,number[]>;reference:Record<string,number[]>}

