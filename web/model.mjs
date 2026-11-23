export const SCHEMA='coolcode.orbitalcensus.v1';
export const FIELDS=['NORAD_CAT_ID','OBJECT_NAME','OBJECT_ID','OBJECT_TYPE','OPS_STATUS_CODE','OWNER','LAUNCH_DATE','LAUNCH_SITE','DECAY_DATE','PERIOD','INCLINATION','APOGEE','PERIGEE','RCS','DATA_STATUS_CODE','ORBIT_CENTER','ORBIT_TYPE'];
export const LABELS={NORAD_CAT_ID:'NORAD catalogue number',OBJECT_NAME:'Object name',OBJECT_ID:'International designator',OBJECT_TYPE:'Object type',OPS_STATUS_CODE:'Operational status',OWNER:'Owner code',LAUNCH_DATE:'Launch date',LAUNCH_SITE:'Launch site',DECAY_DATE:'Decay date',PERIOD:'Period (minutes)',INCLINATION:'Inclination (degrees)',APOGEE:'Apogee (km)',PERIGEE:'Perigee (km)',RCS:'Radar cross section (m²)',DATA_STATUS_CODE:'Element-data status',ORBIT_CENTER:'Orbit centre',ORBIT_TYPE:'Orbit type'};
export const TYPES={PAY:'Payload', 'R/B':'Rocket body',DEB:'Debris',UNK:'Unknown'};
export const OPS={'+':'Operational','-':'Nonoperational',P:'Partially operational',B:'Backup / standby',S:'Spare',X:'Extended mission',D:'Decayed / deorbited','?':'Unknown'};
export const OWNERS={CA:'Canada',US:'United States',CIS:'CIS / former USSR',PRC:'China',JPN:'Japan',IND:'India',FR:'France',UK:'United Kingdom',ESA:'European Space Agency',ISS:'International Space Station',GER:'Germany'};
export function ownerLabel(code){return OWNERS[code]?`${OWNERS[code]} (${code})`:code||'Unknown';}
export function validateReceipt(data){
 if(!data||data.schema!==SCHEMA||!Array.isArray(data.fields)||JSON.stringify(data.fields)!==JSON.stringify(FIELDS)||!Array.isArray(data.rows)||data.rows.length>500000)throw Error('This is not a supported Orbital Census receipt.');
 if(!/^\d{4}-\d{2}-\d{2}T/.test(data.capturedAt)||!Number.isFinite(Date.parse(data.capturedAt))||!Number.isFinite(Date.parse(data.sourceUpdatedAt)))throw Error('The receipt needs valid capture and source edition dates.');
 if(!data.coverage||!Array.isArray(data.coverage.owners)||!Array.isArray(data.coverage.objectTypes)||![...data.coverage.owners,...data.coverage.objectTypes].every(v=>typeof v==='string'))throw Error('The receipt is missing its coverage definition.');
 if(!Number.isSafeInteger(data.sourceRecordCount)||data.sourceRecordCount<data.rows.length)throw Error('Invalid source record count.');
 const seen=new Set();
 for(const row of data.rows){if(!Array.isArray(row)||row.length!==FIELDS.length||!row.every(v=>typeof v==='string'&&v.length<=1000)||!/^\d{1,9}$/.test(row[0])||Number(row[0])<1||seen.has(row[0])||!row[1]||!TYPES[row[3]])throw Error('A receipt row is incomplete, invalid or duplicated.');seen.add(row[0]);}
 return data;
}
export function unpack(receipt){validateReceipt(receipt);return receipt.rows.map(row=>Object.fromEntries(FIELDS.map((key,index)=>[key,row[index]])));}
export function hasDecay(row){return Boolean(row.DECAY_DATE)||row.OPS_STATUS_CODE==='D';}
export function isActive(row){return row.OBJECT_TYPE==='PAY'&&['+','P','B','S','X'].includes(row.OPS_STATUS_CODE);}
export function yearOf(row){return /^\d{4}-\d{2}-\d{2}/.test(row.LAUNCH_DATE)?Number(row.LAUNCH_DATE.slice(0,4)):null;}
export function filterRows(rows,filters={}){const q=(filters.query||'').trim().toLowerCase();return rows.filter(r=>{const year=yearOf(r);return (!q||[r.OBJECT_NAME,r.OBJECT_ID,r.NORAD_CAT_ID,ownerLabel(r.OWNER)].some(v=>v.toLowerCase().includes(q)))&&(!filters.owner||r.OWNER===filters.owner)&&(!filters.type||r.OBJECT_TYPE===filters.type)&&(!filters.yearMin||(year!==null&&year>=Number(filters.yearMin)))&&(!filters.yearMax||(year!==null&&year<=Number(filters.yearMax)))&&(!filters.status||(filters.status==='decayed'?hasDecay(r):filters.status==='no-decay'?!hasDecay(r):isActive(r)));});}
export function summary(rows){return {objects:rows.length,payloads:rows.filter(r=>r.OBJECT_TYPE==='PAY').length,active:rows.filter(isActive).length,decayed:rows.filter(hasDecay).length,launches:new Set(rows.map(r=>r.OBJECT_ID.match(/^\d{4}-\d{3}/)?.[0]).filter(Boolean)).size};}
export function groupCounts(rows,key){const counts=new Map();for(const row of rows){const value=typeof key==='function'?key(row):row[key]||'Unknown';counts.set(value,(counts.get(value)||0)+1);}return [...counts].map(([name,count])=>({name,count})).sort((a,b)=>b.count-a.count||String(a.name).localeCompare(String(b.name)));}
export function comparable(a,b){return JSON.stringify([...a.coverage.owners].sort())===JSON.stringify([...b.coverage.owners].sort())&&JSON.stringify([...a.coverage.objectTypes].sort())===JSON.stringify([...b.coverage.objectTypes].sort());}
export function compare(a,b,fields){
 if(!comparable(a,b))throw Error('These captures use different coverage selections. Compare captures with the same coverage to avoid mistaking scope changes for catalogue removals.');
 if(!Array.isArray(fields)||!fields.length||fields.some(k=>!FIELDS.includes(k)))throw Error('Choose known comparison fields.');
 const older=new Map(unpack(a).map(r=>[r.NORAD_CAT_ID,r])),newer=new Map(unpack(b).map(r=>[r.NORAD_CAT_ID,r]));
 const added=[],removed=[],changed=[];
 for(const [id,row]of newer){if(!older.has(id))added.push(row);else{const prior=older.get(id),changes=fields.filter(k=>prior[k]!==row[k]).map(field=>({field,before:prior[field],after:row[field]}));if(changes.length)changed.push({id,name:row.OBJECT_NAME,changes});}}
 for(const [id,row]of older)if(!newer.has(id))removed.push(row);
 return {added,removed,changed};
}
export function safeCapturePath(file){if(typeof file!=='string'||!/^captures\/[\dTZ]+-[a-f0-9]{10}\.json\.gz$/.test(file))throw Error('Invalid capture filename.');return './data/'+file;}
export function csv(rows){const esc=value=>'"'+String(value??'').replaceAll('"','""')+'"';return FIELDS.map(esc).join(',')+'\r\n'+rows.map(row=>FIELDS.map(k=>esc((/^[=+@\t\r]/.test(row[k])||(/^-/.test(row[k])&&!/^-\d+(?:\.\d+)?$/.test(row[k])))?"'"+row[k]:row[k])).join(',')).join('\r\n');}
