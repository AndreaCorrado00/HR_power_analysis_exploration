// Exercise the frontend against the real ECharts SVG renderer, without a browser.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const echarts = require('./vendor/echarts.min.js');
const elements = new Map();
const element = id => {
  if(!elements.has(id))elements.set(id,{textContent:'',hidden:false,disabled:false,handlers:{},addEventListener(event,handler){this.handlers[event]=handler;}});
  return elements.get(id);
};
const actualChart = echarts.init(null,null,{renderer:'svg',ssr:true,width:1200,height:720});
const workouts = [
  {id:'260101120000',samples:4,start_s:0,end_s:100,segments:[{rows:[[0,204,200,202,4,2,0,-1],[1,206,200,204,6,4,1,0]]},
    {rows:[[90,202,200,206,2,6,-1,1],[100,208,200,210,8,10,2,3]]}]},
  {id:'260102120000',samples:2,start_s:0,end_s:60,segments:[{rows:[[0,304,300,302,4,2,0,-1],[60,308,300,306,8,6,2,1]]}]}
];
for(const w of workouts)w.acf={paths:100,rows:[[1,.5,.3,.4,.5,10],[2,.2,.1,.2,.3,8]]};
const catalog={model:{p:2,residual_mean_w:4,residual_sd_w:2},workouts:workouts.map((w,i)=>({id:w.id,date:`0${i+1}/01/2026`}))};
const context = vm.createContext({
  echarts:{init:()=>actualChart},document:{getElementById:element},console,
  ResizeObserver:class{observe(){}},
  fetch:async url=>({ok:true,json:async()=>url==='/api/workouts'?catalog:workouts.find(w=>url.endsWith(w.id))})
});
async function ready(){for(let i=0;i<100;i++){await new Promise(resolve=>setTimeout(resolve,5));if(!vm.runInContext('loading',context)&&vm.runInContext('current != null',context))return;}throw Error('UI failed to load');}
(async()=>{
  try {
    vm.runInContext(fs.readFileSync(path.join(__dirname,'app.js'),'utf8'),context);
    await ready();
    assert.equal(element('counter').textContent,'1 / 2');
    assert.equal(element('previous').disabled,true);
    assert.equal(actualChart.getOption().series.length,9);
    const curves=actualChart.getOption().series;
    assert.deepEqual(Array.from(curves[0].data[2]),[45.5,null]); // no line across a gap
    assert.deepEqual(Array.from(curves[5].data[0]),[1,.5]);
    assert.deepEqual(Array.from(curves[6].data[0]),[1,.4]);
    actualChart.dispatchAction({type:'dataZoom',dataZoomIndex:0,startValue:10,endValue:80});
    for(let i=0;i<2;i++)assert.deepEqual(actualChart.getModel().getComponent('xAxis',i).axis.scale.getExtent(),[10,80]);
    actualChart.dispatchAction({type:'dataZoom',dataZoomIndex:1,startValue:30,endValue:60});
    for(let i=0;i<2;i++)assert.deepEqual(actualChart.getModel().getComponent('xAxis',i).axis.scale.getExtent(),[30,60]);
    assert.deepEqual(actualChart.getModel().getComponent('xAxis',2).axis.scale.getExtent(),[0,2]);
    element('reset').handlers.click();
    for(let i=0;i<2;i++)assert.deepEqual(actualChart.getModel().getComponent('xAxis',i).axis.scale.getExtent(),[0,100]);
    actualChart.getOption().tooltip[0].formatter([{value:[90,202]}]);
    assert.equal(element('value-time').textContent,'00:01:30');
    assert.equal(element('value-real').textContent,'202,00 W');
    assert.equal(element('value-residual').textContent,'2,00 / 6,00 W');
    assert.equal(element('value-z').textContent,'-1,000 / 1,000');
    assert.equal(vm.runInContext('nearest(40)',context),null);
    await element('next').handlers.click();
    assert.equal(element('counter').textContent,'2 / 2');
    assert.equal(element('next').disabled,true);
    assert.equal(element('previous').disabled,false);
    assert.equal(actualChart.getModel().getComponent('xAxis',0).axis.scale.getExtent()[1],60);
    await element('previous').handlers.click();
    assert.equal(element('counter').textContent,'1 / 2');
    const svg=actualChart.renderToSVGString();
    assert(svg.includes('ACF'));
    assert(svg.includes('Potenza [W]'));
    console.log('PASS: real ECharts rendering, linked zoom/pan ranges, reset, gap breaks, values, standardization and workout arrows');
  }finally{actualChart.dispose();}
})().catch(error=>{console.error(error);process.exitCode=1;});
