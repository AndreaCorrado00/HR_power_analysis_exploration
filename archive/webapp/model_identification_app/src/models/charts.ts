export function boxSummary(input:number[]) {
  const v=input.filter(Number.isFinite).sort((a,b)=>a-b)
  if(!v.length)return null
  function q(p:number){const pos=(v.length-1)*p,i=Math.floor(pos);return v[i]+(v[Math.min(i+1,v.length-1)]-v[i])*(pos-i)}
  const q1=q(.25),q3=q(.75),iqr=q3-q1
  const inside=v.filter(n=>n>=q1-1.5*iqr&&n<=q3+1.5*iqr)
  return {box:[inside[0],q1,q(.5),q3,inside[inside.length-1]],outliers:v.filter(n=>n<q1-1.5*iqr||n>q3+1.5*iqr),n:v.length}
}
export function compatibleParameters(a:{key:string;unit:string}[],b:{key:string;unit:string}[]) {return a.filter(p=>b.some(q=>q.key===p.key&&q.unit===p.unit))}
