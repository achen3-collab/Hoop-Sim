const CATS=[{key:"FG_PCT",label:"FG%",pct:true},{key:"FT_PCT",label:"FT%",pct:true},{key:"FG3M",label:"3PTM"},{key:"PTS",label:"PTS"},{key:"REB",label:"REB"},{key:"AST",label:"AST"},{key:"STL",label:"ST"},{key:"BLK",label:"BLK"},{key:"TOV",label:"TO",inverse:true}];
const BASE_SLOTS=["PG","SG","G","SF","PF","F","C1","C2","Util1","Util2","BN1","BN2","BN3"],GROUPS={G:["PG","SG"],F:["SF","PF"]},KEY="hoopsim-v1";
let players=[],loaded=false,toastTimer,activeLineupDate="",scheduleGames=[],scheduleSeason="",dataSeason="2025-26";
function initial(){try{const x=JSON.parse(localStorage.getItem(KEY));if(x?.teams?.length)return x}catch(e){console.warn(e)}return{teams:[{id:"team-1",name:"My Team",playerIds:[],rosterSize:13,lineup:{}},{id:"team-2",name:"Team 2",playerIds:[],rosterSize:13,lineup:{}}],selectedTeamId:"team-1"}}
let state=initial();
state.matchupLineupsByTeam??={};
state.matchupAutoSetByTeam??={};
const save=()=>{if(activeLineupDate){let t=state.teams.find(x=>x.id===state.selectedTeamId);t.lineupsByDate??={};t.lineupsByDate[activeLineupDate]={...t.lineup}}localStorage.setItem(KEY,JSON.stringify(state))},team=()=>state.teams.find(t=>t.id===state.selectedTeamId)||state.teams[0],slots=t=>[...BASE_SLOTS,...Array.from({length:Math.max(0,Number(t.rosterSize)-13)},(_,i)=>`BN${i+4}`)],slotLabel=s=>s.startsWith("C")?"C":s.startsWith("Util")?"Util":s.startsWith("BN")?"BN":s,player=id=>players.find(p=>String(p.id)===String(id)),roster=t=>t.playerIds.map(player).filter(Boolean),n=(p,k)=>Number(p?.stats?.[k]??p?.[k]??0)||0;
function esc(x){return String(x??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function pos(p){let raw=p?.positions;if(!Array.isArray(raw)||!raw.length)raw=p?.position??raw??[];if(!Array.isArray(raw))raw=[raw];let output=new Set();for(let value of raw){let tokens=String(value||"").toUpperCase().replace(/\bPOINT\s+GUARD\b/g,"PG").replace(/\bSHOOTING\s+GUARD\b/g,"SG").replace(/\bSMALL\s+FORWARD\b/g,"SF").replace(/\bPOWER\s+FORWARD\b/g,"PF").replace(/\bGUARD\b/g,"G").replace(/\bFORWARD\b/g,"F").split(/[^A-Z]+/);for(let token of tokens){if(["PG","SG","G"].includes(token))output.add("G");else if(["SF","PF","F"].includes(token))output.add("F");else if(token==="C")output.add("C")}}return[...output]}function eligible(p,s){let label=slotLabel(s);if(!p||label==="BN"||label==="Util")return!!p;let group=label==="PG"||label==="SG"||label==="G"?"G":label==="SF"||label==="PF"||label==="F"?"F":label;return pos(p).includes(group)}
function slotPlayer(t,s){return t.lineup?.[s]&&t.playerIds.some(x=>String(x)===String(t.lineup[s]))?player(t.lineup[s]):null}
function toast(text){let el=document.querySelector("#toast");el.textContent=text;el.classList.add("show");clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove("show"),2200)}
function pct(x){return`${(x*100).toFixed(1)}%`}function cell(p,k){return p&&n(p,"GP")?n(p,k).toFixed(1):"–"}
function renderPool(){let body=document.querySelector("#player-rows"),q=document.querySelector("#player-search").value.toLowerCase().trim(),position=document.querySelector("#position-filter").value,all=document.querySelector("#availability-filter").value==="all",drafted=new Set(state.teams.flatMap(t=>t.playerIds.map(String)));let list=players.filter(p=>(p.name||"").toLowerCase().includes(q)&&(!position||pos(p).includes(position))&&(all||!drafted.has(String(p.id)))).sort((a,b)=>(a.name||"").localeCompare(b.name||""));document.querySelector("#player-pool-count").textContent=loaded?list.length:0;body.innerHTML=list.map(p=>`<tr draggable="true" data-pid="${esc(p.id)}"><td><span class="player-name">${esc(p.name)}</span><span class="player-meta">${esc(p.team||"NBA")}</span></td><td class="position-tags">${esc(pos(p).join("/")||"–")}</td><td>${n(p,"GP")||"–"}</td><td>${cell(p,"PTS")}</td><td>${cell(p,"REB")}</td><td>${cell(p,"AST")}</td><td>${cell(p,"STL")}</td><td>${cell(p,"BLK")}</td><td>${cell(p,"FG3M")}</td><td><button class="add-player" data-add="${esc(p.id)}" aria-label="Draft ${esc(p.name)}" ${drafted.has(String(p.id))||team().playerIds.length>=team().rosterSize?"disabled":""}>+</button></td></tr>`).join("");document.querySelector("#player-empty").classList.toggle("visible",loaded&&!list.length);body.parentElement.style.display=loaded&&list.length?"":"none";body.querySelectorAll("[data-add]").forEach(b=>b.onclick=()=>draft(b.dataset.add));body.querySelectorAll("tr[draggable]").forEach(r=>r.ondragstart=e=>e.dataTransfer.setData("text/player-id",r.dataset.pid))}
function draft(id,target){let t=team(),p=player(id);if(!p||t.playerIds.some(x=>String(x)===String(id)))return;if(t.playerIds.length>=t.rosterSize)return toast("Roster is full. Remove a player first.");if(target&&!eligible(p,target))return toast(`${p.name} is not eligible at ${slotLabel(target)}.`);t.playerIds.push(p.id);let dest=target||slots(t).find(s=>slotLabel(s)!=="BN"&&!slotPlayer(t,s)&&eligible(p,s));if(dest)t.lineup[dest]=p.id;save();render();toast(`${p.name} added to ${t.name}.`)}
function remove(id){let t=team();t.playerIds=t.playerIds.filter(x=>String(x)!==String(id));for(let s of Object.keys(t.lineup))if(String(t.lineup[s])===String(id))delete t.lineup[s];save();render()}
function assign(id,s){let t=team(),p=player(id);if(!p)return;if(!t.playerIds.some(x=>String(x)===String(id)))return draft(id,s);if(!eligible(p,s))return toast(`${p.name} is not eligible at ${s}.`);let old=Object.keys(t.lineup).find(x=>String(t.lineup[x])===String(id)),occupied=t.lineup[s];if(old&&old!==s)delete t.lineup[old];if(occupied&&String(occupied)!==String(id)){if(old)t.lineup[old]=occupied;else delete t.lineup[s]}t.lineup[s]=id;save();render()}
function gamesForPlayer(p,date){if(dataSeason==="2026-27"&&p?.rosterSeason!=="2026-27")return null;let aggregate=new Set(["TOT","2TM","3TM","4TM"]),logs=(p?.gameLogs||[]).filter(log=>log.date<=date).sort((a,b)=>a.date.localeCompare(b.date)),team=aggregate.has(p?.team)?logs.at(-1)?.team:p?.team;if(!team||aggregate.has(team))return null;return{team,games:scheduleGames.filter(game=>game.date===date&&game.teams?.includes(team))}}
function dailyGameCell(p){if(!p)return`<td class="schedule-game">–</td>`;let projection=gamesForPlayer(p,document.querySelector("#lineup-date").value);if(projection===null)return`<td class="schedule-game"><span title="Import player game logs to resolve traded-team assignments">Team TBD</span></td>`;if(!projection.games.length)return`<td class="schedule-game">–</td>`;return`<td class="schedule-game">${projection.games.map(game=>{let index=game.teams.indexOf(projection.team),opponent=game.teams[index===0?1:0];return`<span>${index===0?"@":"vs"} ${esc(opponent)}</span>`}).join(" ")}</td>`}
function renderRoster(target="#roster-rows",t=team()){let body=document.querySelector(target),ss=slots(t),showGame=target==="#daily-roster-rows";body.innerHTML=ss.map((s,i)=>{let p=slotPlayer(t,s),label=slotLabel(s);return`<tr class="roster-row ${p?"":"empty"}" data-slot="${s}"><td><span class="slot-badge">${label}</span></td><td>${p?`<span class="roster-player">${esc(p.name)}</span><span class="roster-sub">${esc(p.team||"")}</span>`:`<span class="drop-placeholder">${label==="BN"?"Bench":"Drag eligible player here"}</span>`}</td>${showGame?dailyGameCell(p):""}<td class="position-tags">${p?esc(pos(p).join("/")):""}</td><td>${cell(p,"PTS")}</td><td>${cell(p,"REB")}</td><td>${cell(p,"AST")}</td><td>${cell(p,"EFF")}</td><td>${p?pct(n(p,"FG_PCT")):""}</td><td>${p?pct(n(p,"FT_PCT")):""}</td><td>${cell(p,"FG3M")}</td><td>${p?`<button class="remove-player" data-remove="${esc(p.id)}" aria-label="Remove ${esc(p.name)}">×</button>`:""}</td></tr>`}).join("");body.querySelectorAll("[data-remove]").forEach(b=>b.onclick=()=>remove(b.dataset.remove));body.querySelectorAll(".roster-row").forEach(r=>{r.ondragover=e=>{e.preventDefault();r.classList.add("drag-over")};r.ondragleave=()=>r.classList.remove("drag-over");r.ondrop=e=>{e.preventDefault();r.classList.remove("drag-over");assign(e.dataTransfer.getData("text/player-id"),r.dataset.slot)}});body.querySelectorAll(".roster-player").forEach((el,i)=>{let id=t.lineup?.[ss[i]];if(id){el.draggable=true;el.ondragstart=e=>e.dataTransfer.setData("text/player-id",id)}})}
function aggregate(list){let a=Object.fromEntries(CATS.map(c=>[c.key,0])),fm=0,fa=0,tm=0,ta=0;for(let p of list){for(let c of CATS)if(!c.pct)a[c.key]+=n(p,c.key);let gp=n(p,"GP")||1;fm+=n(p,"FGM")/gp;fa+=n(p,"FGA")/gp;tm+=n(p,"FTM")/gp;ta+=n(p,"FTA")/gp}a.FG_PCT=fa?fm/fa:0;a.FT_PCT=ta?tm/ta:0;return a}
function baseline(key){let vals=players.map(p=>n(p,key)).filter(x=>x>0).sort((a,b)=>a-b);if(!vals.length)return 0;let med=vals[Math.floor(vals.length/2)];return CATS.find(c=>c.key===key).pct?med:med*Math.max(1,roster(team()).length)}
function renderCats(){
  let rosterPlayers=roster(team()),totals=aggregate(rosterPlayers);
  let width=360,height=290,cx=width/2,cy=height/2,radius=91,labelRadius=radius+22;
  let point=(index,r)=>{let angle=-Math.PI/2+index*2*Math.PI/CATS.length;return{x:cx+Math.cos(angle)*r,y:cy+Math.sin(angle)*r}};
  let values=CATS.map((category,index)=>{
    let reference=baseline(category.key),edge=category.pct
      ?totals[category.key]-reference
      :(totals[category.key]-reference)/Math.max(1,reference);
    if(category.inverse)edge*=-1;
    let scale=category.pct?0.1:0.5,score=Math.max(-1,Math.min(1,edge/scale));
    let text=category.pct
      ?`${edge>=0?"+":""}${(edge*100).toFixed(1)} pp`
      :`${edge>=0?"+":""}${(edge*100).toFixed(0)}%`;
    return{category,edge,score,text,point:point(index,radius*(1+score)/2),label:point(index,labelRadius)};
  });
  let rings=[.25,.5,.75,1].map(fraction=>`<circle class="radar-ring ${fraction===.5?"baseline":""}" cx="${cx}" cy="${cy}" r="${(radius*fraction).toFixed(1)}"/>`).join("");
  let axes=CATS.map((_,index)=>{let end=point(index,radius);return`<line class="radar-axis" x1="${cx}" y1="${cy}" x2="${end.x.toFixed(1)}" y2="${end.y.toFixed(1)}"/>`}).join("");
  let polygon=values.map(value=>`${value.point.x.toFixed(1)},${value.point.y.toFixed(1)}`).join(" ");
  let labels=values.map(({category,edge,score,text,label},index)=>{
    let anchor=label.x<cx-8?"end":label.x>cx+8?"start":"middle",tone=score>=0?"strength":"weakness";
    let y=label.y+(index===0?-2:12);
    return`<text class="radar-label ${tone}" x="${label.x.toFixed(1)}" y="${y.toFixed(1)}" text-anchor="${anchor}"><tspan>${category.label}</tspan><tspan class="radar-value" x="${label.x.toFixed(1)}" dy="11">${rosterPlayers.length?text:"–"}</tspan></text>`;
  }).join("");
  let markers=values.map(({category,edge,score,point})=>`<circle class="radar-point ${score>=0?"strength":"weakness"}" cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="4"><title>${category.label}: ${rosterPlayers.length?`${edge>=0?"+":""}${category.pct?(edge*100).toFixed(1)+" percentage points":(edge*100).toFixed(0)+"%"} vs league median`:"No players drafted"}</title></circle>`).join("");
  document.querySelector("#category-list").innerHTML=`<svg class="radar-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Team category radar chart. Values beyond the middle ring are strengths; values inside are weaknesses.">${rings}${axes}<polygon class="radar-area" points="${polygon}"/>${markers}${labels}</svg>${rosterPlayers.length?"":'<p class="radar-empty">Draft players to compare your category profile.</p>'}`;
}
function weekDate(){let d=new Date((document.querySelector("#week-start").value||new Date().toISOString().slice(0,10))+"T12:00:00");d.setDate(d.getDate()-(d.getDay()+6)%7);return d}
function project(t,start){let out=Object.fromEntries(CATS.map(c=>[c.key,0])),fm=0,fa=0,tm=0,ta=0,starters=slots(t).filter(s=>s!=="BN").map(s=>slotPlayer(t,s)).filter(Boolean);for(let p of starters){let logs=p.gameLogs||[],end=new Date(start);end.setDate(end.getDate()+7);let games=logs.filter(g=>{let d=new Date(g.date+"T12:00:00");return d>=start&&d<end});if(!games.length){for(let c of CATS)if(!c.pct)out[c.key]+=n(p,c.key)*3.5;let gp=Math.max(1,n(p,"GP"));fm+=n(p,"FGM")/gp*3.5;fa+=n(p,"FGA")/gp*3.5;tm+=n(p,"FTM")/gp*3.5;ta+=n(p,"FTA")/gp*3.5}else{for(let c of CATS)if(!c.pct)out[c.key]+=games.reduce((sum,g)=>sum+Number(g[c.key]||0),0);fm+=games.reduce((sum,g)=>sum+Number(g.FGM||0),0);fa+=games.reduce((sum,g)=>sum+Number(g.FGA||0),0);tm+=games.reduce((sum,g)=>sum+Number(g.FTM||0),0);ta+=games.reduce((sum,g)=>sum+Number(g.FTA||0),0)}}out.FG_PCT=fa?fm/fa:0;out.FT_PCT=ta?tm/ta:0;return{out,count:starters.length}}
function renderMatchup(){let opp=state.teams.find(t=>t.id===document.querySelector("#opponent-select").value)||state.teams.find(t=>t.id!==team().id),start=weekDate(),generated=false;for(let target of [team(),opp].filter(Boolean)){if(state.matchupAutoSetByTeam[target.id]&&scheduleSeason===dataSeason&&scheduleGames.length){autoSetMatchupWeek(target);generated=true}}if(generated)localStorage.setItem(KEY,JSON.stringify(state));let mySwitch=document.querySelector("#auto-set-my-matchup"),opponentSwitch=document.querySelector("#auto-set-opponent-matchup");mySwitch.checked=!!state.matchupAutoSetByTeam[team().id];opponentSwitch.checked=!!(opp&&state.matchupAutoSetByTeam[opp.id]);opponentSwitch.disabled=!opp;for(let input of [mySwitch,opponentSwitch])input.parentElement.querySelector(".switch-state").textContent=input.checked?"On":"Off";let a=project(team(),start),b=opp?project(opp,start):{out:{},count:0},wins=0,loss=0;document.querySelector("#matchup-opponent-name").textContent=opp?.name||"No opponent";document.querySelector("#my-category-heading").textContent=team().name.toUpperCase();document.querySelector("#opponent-category-heading").textContent=opp?.name.toUpperCase()||"OPPONENT";document.querySelector("#matchup-rows").innerHTML=CATS.map(c=>{let l=a.out[c.key]||0,r=b.out[c.key]||0,left=c.inverse?l<r:l>r,tie=Math.abs(l-r)<.0001,w=tie?"TIE":left?team().name:opp?.name;if(tie){}else if(left)wins++;else loss++;let edge=c.pct?`${((l-r)*100).toFixed(1)} pp`:(l-r).toFixed(1),fmt=x=>c.pct?pct(x):x.toFixed(1);return`<tr><td>${c.label}</td><td>${fmt(l)}</td><td>${edge}</td><td>${fmt(r)}</td><td><span class="match-winner ${tie?"tie":""}">${esc(w||"–")}</span></td></tr>`}).join("");document.querySelector("#category-score").textContent=`${wins} – ${loss}`;document.querySelector("#my-record").textContent=`${a.count} ACTIVE STARTERS`;renderLineupChanges(team(),opp,start)}
function matchupDates(start){return Array.from({length:7},(_,index)=>{let date=new Date(start);date.setDate(date.getDate()+index);return date})}
function matchupDateKey(date){return`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`}
function savedLineup(t,date){return t.lineupsByDate?.[date]||t.lineup||{}}
function assumedLineup(t,date){return state.matchupAutoSetByTeam?.[t.id]?state.matchupLineupsByTeam?.[t.id]?.[date]||savedLineup(t,date):savedLineup(t,date)}
function activeLineupPlayers(t,assignment){return slots(t).filter(slot=>slotLabel(slot)!=="BN").map(slot=>assignment[slot]).filter(Boolean).map(String)}
function autoSetMatchupWeek(t){
  if(scheduleSeason!==dataSeason||!scheduleGames.length)return toast(`${dataSeason} schedule is unavailable.`);
  state.matchupLineupsByTeam??={};
  let previous=assumedLineup(t,matchupDateKey(new Date(weekDate().getTime()-86400000)));
  let week=state.matchupLineupsByTeam[t.id]??{};
  for(let date of matchupDates(weekDate())){
    let key=matchupDateKey(date),activeSlots=slots(t).filter(slot=>slotLabel(slot)!=="BN"),playersOnRoster=roster(t);
    let previousIds=new Set(activeLineupPlayers(t,previous));
    let ordered=playersOnRoster.sort((left,right)=>{
      let leftGame=!!gamesForPlayer(left,key)?.games.length,rightGame=!!gamesForPlayer(right,key)?.games.length;
      if(leftGame!==rightGame)return leftGame?-1:1;
      let leftActive=previousIds.has(String(left.id)),rightActive=previousIds.has(String(right.id));
      if(leftActive!==rightActive)return leftActive?-1:1;
      let leftOptions=activeSlots.filter(slot=>eligible(left,slot)).length,rightOptions=activeSlots.filter(slot=>eligible(right,slot)).length;
      return leftOptions-rightOptions||(left.name||"").localeCompare(right.name||"");
    });
    let assignment={},match=(person,visited)=>{
      for(let slot of activeSlots){
        if(visited.has(slot)||!eligible(person,slot))continue;
        visited.add(slot);
        let occupant=assignment[slot]&&player(assignment[slot]);
        if(!occupant||match(occupant,visited)){assignment[slot]=person.id;return true}
      }
      return false;
    };
    for(let person of ordered)match(person,new Set());
    week[key]=assignment;
    previous=assignment;
  }
  state.matchupLineupsByTeam[t.id]=week;
}
function renderLineupChanges(myTeam,opponent,start){
  let container=document.querySelector("#lineup-changes-content");
  if(!container)return;
  if(!opponent){container.innerHTML='<p class="lineup-changes-empty">Add or select an opponent to compare daily lineups.</p>';return}
  let dates=matchupDates(start);
  let teamSection=(t)=>{
    let lines=dates.map((date,index)=>{
      let key=matchupDateKey(date),ids=activeLineupPlayers(t,assumedLineup(t,key)),prior=index?activeLineupPlayers(t,assumedLineup(t,matchupDateKey(dates[index-1]))):ids;
      let before=new Set(prior),after=new Set(ids),added=ids.filter(id=>!before.has(id)),removed=prior.filter(id=>!after.has(id)),playersLabel=list=>list.map(id=>player(id)?.name||id).map(esc).join(", ");
      let dayDetail=index===0?"Starts the week":added.length||removed.length?`${added.length?`+ ${playersLabel(added)}`:""}${added.length&&removed.length?" · ":""}${removed.length?`− ${playersLabel(removed)}`:""}`:"No changes from previous day",details=[`vs previous day: ${dayDetail}`];
      if(state.matchupAutoSetByTeam[t.id]){
        let actual=activeLineupPlayers(t,savedLineup(t,key)),actualSet=new Set(actual),currentSet=new Set(ids),autoAdded=ids.filter(id=>!actualSet.has(id)),autoRemoved=actual.filter(id=>!currentSet.has(id));
        details.push(`Auto-set vs saved: ${autoAdded.length?`+ ${playersLabel(autoAdded)}`:""}${autoAdded.length&&autoRemoved.length?" · ":""}${autoRemoved.length?`− ${playersLabel(autoRemoved)}`:""}${!autoAdded.length&&!autoRemoved.length?"No difference":""}`);
      }
      return`<li><time datetime="${key}">${date.toLocaleDateString(undefined,{weekday:"short",month:"short",day:"numeric"})}</time><span>${details.join("<br>")}</span></li>`;
    }).join("");
    return`<section class="lineup-change-team"><h3>${esc(t.name)}</h3><ol>${lines}</ol></section>`;
  };
  container.innerHTML=`${teamSection(myTeam)}${teamSection(opponent)}`;
}
function render(){
  let t=team(),sel=document.querySelector("#team-select");
  sel.innerHTML=state.teams.map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join("");
  sel.value=t.id;
  document.querySelector("#team-count").textContent=state.teams.length;
  document.querySelector("#active-team-label").textContent=t.name;
  document.querySelector("#roster-size").value=t.rosterSize;
  document.querySelector("#roster-count").textContent=`${t.playerIds.length} / ${t.rosterSize}`;
  document.querySelector("#roster-progress-fill").style.width=`${Math.min(100,t.playerIds.length/t.rosterSize*100)}%`;
  let os=document.querySelector("#opponent-select");
  os.innerHTML=state.teams.filter(x=>x.id!==t.id).map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join("");
  document.querySelector("#daily-team-name").textContent=t.name;
  document.querySelector("#matchup-my-name").textContent=t.name;
  renderRoster();
  renderRoster("#daily-roster-rows");
  renderCats();
  renderPool();
  renderMatchup();
}
function bestFit(t){let rem=roster(t).slice(),out={};for(let s of slots(t).filter(x=>x!=="BN")){let i=rem.findIndex(p=>eligible(p,s));if(i>=0)out[s]=rem.splice(i,1)[0].id}return out}
function mergePools(pools){let merged=new Map(),seasonRank={"2024-25":0,"2025-26":1,"2026-27":2};for(let pool of pools.sort((a,b)=>(seasonRank[a.season]??0)-(seasonRank[b.season]??0))){for(let candidate of pool.players||[]){let id=String(candidate.id),previous=merged.get(id),candidateHasStats=Number(candidate.stats?.GP??candidate.GP??0)>0,previousHasStats=Number(previous?.stats?.GP??previous?.GP??0)>0,candidateSeason=candidate.statsSeason||candidate.season||pool.season,previousSeason=previous?.statsSeason||previous?.season||"",useCandidateStats=candidateHasStats&&(!previousHasStats||(seasonRank[candidateSeason]??0)>=(seasonRank[previousSeason]??0)),statsSource=useCandidateStats||!previous?candidate:previous,metadataSource=candidate.positions?.length?candidate:previous||candidate,teamSource=candidate.rosterSeason?candidate:previous?.rosterSeason?previous:candidate,logs=candidate.gameLogs?.length?candidate.gameLogs:previous?.gameLogs||[];let result={...statsSource,id:candidate.id,name:candidate.name||previous?.name,team:teamSource.team||previous?.team||"FA",teams:teamSource.teams?.length?teamSource.teams:previous?.teams||[],rosterSeason:teamSource.rosterSeason||previous?.rosterSeason,positions:metadataSource.positions||[],stats:statsSource.stats||{},gameLogs:logs,season:statsSource.season||candidateSeason,statsSeason:statsSource.statsSeason||statsSource.season||candidateSeason};for(let [key,value] of Object.entries(result.stats))result[key]=value;merged.set(id,result)}}return[...merged.values()].sort((a,b)=>(a.name||"").localeCompare(b.name||""))}
async function load(season="2025-26"){try{let seasons=["2024-25","2025-26","2026-27"],pools=(await Promise.all(seasons.map(async value=>{let url=value==="2025-26"?"data/players.json":`data/players-${value}.json`;try{let response=await fetch(`${url}?t=${Date.now()}`);return response.ok?await response.json():null}catch(error){return null}}))).filter(Boolean);if(!pools.length)throw Error("No imported player pools found");players=mergePools(pools);loaded=true;document.querySelector("#sync-dot").className="sync-dot ok";document.querySelector("#sync-status").textContent=`${players.length.toLocaleString()} players · latest stats across ${pools.map(pool=>pool.season).join(", ")}`;let timestamps=pools.map(pool=>pool.lastSyncedAt).filter(Boolean).sort();document.querySelector("#sync-stamp").textContent=timestamps.length?`Latest sync ${new Date(timestamps[timestamps.length-1]).toLocaleString()}`:"Sync timestamp unavailable";document.querySelector(".page-heading .eyebrow").textContent=`LATEST STATS · SCHEDULE ${season.replace("-","–")}`}catch(error){players=[];loaded=false;document.querySelector("#sync-dot").className="sync-dot warn";document.querySelector("#sync-status").textContent="No imported NBA player pools found";document.querySelector("#sync-stamp").textContent="Run the local importer to sync data"}render()}
function bind(){document.querySelectorAll(".nav-tab").forEach(b=>b.onclick=()=>{document.querySelectorAll(".nav-tab,.view").forEach(x=>x.classList.remove("active"));b.classList.add("active");document.querySelector(`#view-${b.dataset.view}`).classList.add("active");if(b.dataset.view==="matchups")renderMatchup()});document.querySelector("#team-select").onchange=e=>{state.selectedTeamId=e.target.value;save();render()};document.querySelector("#add-team").onclick=()=>{if(state.teams.length>=20)return toast("This league already has 20 teams.");let t={id:`team-${Date.now()}`,name:`Team ${state.teams.length+1}`,playerIds:[],rosterSize:13,lineup:{}};state.teams.push(t);state.selectedTeamId=t.id;save();render()};document.querySelector("#rename-team").onclick=()=>{let name=prompt("Team name",team().name);if(name?.trim()){team().name=name.trim().slice(0,30);save();render()}};document.querySelector("#roster-size").onchange=e=>{team().rosterSize=Number(e.target.value);save();render()};["#player-search","#position-filter","#availability-filter"].forEach(s=>document.querySelector(s).oninput=renderPool);document.querySelector("#clear-filters").onclick=()=>{document.querySelector("#player-search").value="";document.querySelector("#position-filter").value="";document.querySelector("#availability-filter").value="available";renderPool()};document.querySelector("#save-roster").onclick=()=>{save();toast("Roster saved on this device.")};document.querySelector("#save-lineup").onclick=()=>{save();toast("Lineup saved on this device.")};document.querySelector("#restore-lineup").onclick=()=>{team().lineup=bestFit(team());save();render();toast("Best-fit lineup restored.")};document.querySelector("#opponent-select").onchange=renderMatchup;document.querySelector("#week-start").onchange=renderMatchup;document.querySelector("#refresh-data").onclick=()=>load(document.querySelector("#season-select").value);document.querySelector("#season-select").onchange=e=>load(e.target.value)}
function reconcileRoster(t){let changed=false,assigned=new Set();for(let s of slots(t)){let id=t.lineup?.[s];if(!id)continue;if(!t.playerIds.some(x=>String(x)===String(id))||assigned.has(String(id))){delete t.lineup[s];changed=true}else assigned.add(String(id))}for(let p of roster(t)){if(assigned.has(String(p.id)))continue;let dest=slots(t).find(s=>slotLabel(s)!=="BN"&&!t.lineup[s]&&eligible(p,s))||slots(t).find(s=>slotLabel(s)==="BN"&&!t.lineup[s]);if(dest){t.lineup[dest]=p.id;assigned.add(String(p.id));changed=true}}return changed}
const basePool=renderPool,baseRender=render;
draft=function(id,target){let t=team(),p=player(id);if(!p||t.playerIds.some(x=>String(x)===String(id)))return;if(t.playerIds.length>=t.rosterSize)return toast("Roster is full. Remove a player first.");if(target&&!eligible(p,target))return toast(`${p.name} is not eligible at ${slotLabel(target)}.`);let displaced=target&&t.lineup[target],bench=displaced&&slots(t).find(s=>slotLabel(s)==="BN"&&!slotPlayer(t,s)),dest=target||slots(t).find(s=>slotLabel(s)!=="BN"&&!slotPlayer(t,s)&&eligible(p,s))||slots(t).find(s=>slotLabel(s)==="BN"&&!slotPlayer(t,s));if(displaced&&!bench)return toast("No open bench slot for the displaced player.");t.playerIds.push(p.id);if(target){if(displaced)t.lineup[bench]=displaced;t.lineup[target]=p.id}else if(dest)t.lineup[dest]=p.id;save();render();toast(`${p.name} added to ${t.name}.`)};
assign=function(id,s){let t=team(),p=player(id);if(!p)return;if(!t.playerIds.some(x=>String(x)===String(id)))return draft(id,s);if(!eligible(p,s))return toast(`${p.name} is not eligible at ${slotLabel(s)}.`);let old=Object.keys(t.lineup).find(x=>String(t.lineup[x])===String(id)),occupied=t.lineup[s];if(old&&old!==s)delete t.lineup[old];if(occupied&&String(occupied)!==String(id)){let replacement=old||slots(t).find(x=>x!==s&&!t.lineup[x]);if(!replacement)return toast("No open roster slot for the displaced player.");t.lineup[replacement]=occupied}t.lineup[s]=id;save();render()};
renderPool=function(){basePool();let body=document.querySelector("#player-rows");for(let row of body.rows){let p=player(row.dataset.pid);let cell=row.insertCell(3);cell.textContent=p?n(p,"EFF").toFixed(1):"–"}document.querySelector("#player-empty").classList.toggle("visible",!loaded||players.length===0)};
render=function(){
  let current=team();
  if(activeLineupDate&&current.lineupsByDate?.[activeLineupDate])current.lineup={...current.lineupsByDate[activeLineupDate]};
  if(reconcileRoster(current))save();
  baseRender();
  renderWeekSchedule();
};
bestFit=function(t){let remaining=roster(t).slice(),out={};for(let s of slots(t).filter(x=>slotLabel(x)!=="BN")){let i=remaining.findIndex(p=>eligible(p,s));if(i>=0)out[s]=remaining.splice(i,1)[0].id}return out};
function project(t,start){let out=Object.fromEntries(CATS.map(c=>[c.key,0])),fm=0,fa=0,tm=0,ta=0,starters=slots(t).filter(s=>slotLabel(s)!=="BN").map(s=>slotPlayer(t,s)).filter(Boolean);for(let p of starters){let logs=p.gameLogs||[],end=new Date(start);end.setDate(end.getDate()+7);let games=logs.filter(g=>{let d=new Date(g.date+"T12:00:00");return d>=start&&d<end});if(!games.length){for(let c of CATS)if(!c.pct)out[c.key]+=n(p,c.key)*3.5;let gp=Math.max(1,n(p,"GP"));fm+=n(p,"FGM")/gp*3.5;fa+=n(p,"FGA")/gp*3.5;tm+=n(p,"FTM")/gp*3.5;ta+=n(p,"FTA")/gp*3.5}else{for(let c of CATS)if(!c.pct)out[c.key]+=games.reduce((sum,g)=>sum+Number(g[c.key]||0),0);fm+=games.reduce((sum,g)=>sum+Number(g.FGM||0),0);fa+=games.reduce((sum,g)=>sum+Number(g.FGA||0),0);tm+=games.reduce((sum,g)=>sum+Number(g.FTM||0),0);ta+=games.reduce((sum,g)=>sum+Number(g.FTA||0),0)}}out.FG_PCT=fa?fm/fa:0;out.FT_PCT=ta?tm/ta:0;return{out,count:starters.length}};
function project(t,start){let out=Object.fromEntries(CATS.map(c=>[c.key,0])),fm=0,fa=0,tm=0,ta=0,starters=slots(t).filter(s=>slotLabel(s)!=="BN").map(s=>slotPlayer(t,s)).filter(Boolean),end=new Date(start);end.setDate(end.getDate()+7);let today=new Date();today.setHours(0,0,0,0);for(let p of starters){let logs=p.gameLogs||[],games=logs.filter(g=>{let d=new Date(g.date+"T12:00:00");return d>=start&&d<end}),scheduleCount=scheduleSeason===dataSeason&&scheduleGames.length?scheduleGames.filter(g=>g.date>=start.toISOString().slice(0,10)&&g.date<end.toISOString().slice(0,10)&&g.teams.includes(p.team)).length:null,targetGames=scheduleCount===null?(end<=today?games.length:3.5):scheduleCount,remaining=Math.max(0,targetGames-games.length),sum=(key)=>games.reduce((total,g)=>total+Number(g[key]||0),0);for(let c of CATS)if(!c.pct)out[c.key]+=sum(c.key)+n(p,c.key)*remaining;let gp=Math.max(1,n(p,"GP"));fm+=sum("FGM")+n(p,"FGM")/gp*remaining;fa+=sum("FGA")+n(p,"FGA")/gp*remaining;tm+=sum("FTM")+n(p,"FTM")/gp*remaining;ta+=sum("FTA")+n(p,"FTA")/gp*remaining}out.FG_PCT=fa?fm/fa:0;out.FT_PCT=ta?tm/ta:0;return{out,count:starters.length}};
const projectSavedLineup=project;
project=function(t,start){
  if(scheduleSeason!==dataSeason||!scheduleGames.length)return projectSavedLineup(t,start);
  let out=Object.fromEntries(CATS.map(category=>[category.key,0])),fm=0,fa=0,tm=0,ta=0,usedPlayers=new Set();
  for(let date of matchupDates(start)){
    let key=matchupDateKey(date),assignment=assumedLineup(t,key);
    let starters=[...new Set(activeLineupPlayers(t,assignment))].map(player).filter(Boolean);
    for(let person of starters){
      usedPlayers.add(String(person.id));
      let actual=(person.gameLogs||[]).filter(game=>game.date===key);
      let scheduled=gamesForPlayer(person,key)?.games.length||0,missing=Math.max(0,scheduled-actual.length);
      for(let category of CATS)if(!category.pct)out[category.key]+=actual.reduce((sum,game)=>sum+Number(game[category.key]||0),0)+n(person,category.key)*missing;
      let gp=Math.max(1,n(person,"GP")),sum=keyName=>actual.reduce((total,game)=>total+Number(game[keyName]||0),0);
      fm+=sum("FGM")+n(person,"FGM")/gp*missing;
      fa+=sum("FGA")+n(person,"FGA")/gp*missing;
      tm+=sum("FTM")+n(person,"FTM")/gp*missing;
      ta+=sum("FTA")+n(person,"FTA")/gp*missing;
    }
  }
  out.FG_PCT=fa?fm/fa:0;
  out.FT_PCT=ta?tm/ta:0;
  return{out,count:usedPlayers.size};
};
function updateMatchupAutoSet(teamId,enabled){
  if(!teamId)return;
  if(enabled){
    if(scheduleSeason!==dataSeason||!scheduleGames.length){toast(`${dataSeason} schedule is unavailable.`);renderMatchup();return}
    let target=state.teams.find(item=>item.id===teamId);
    if(!target)return;
    autoSetMatchupWeek(target);
  }
  state.matchupAutoSetByTeam[teamId]=enabled;
  save();
  renderMatchup();
}
document.querySelector("#auto-set-my-matchup").onchange=event=>updateMatchupAutoSet(team().id,event.target.checked);
document.querySelector("#auto-set-opponent-matchup").onchange=event=>updateMatchupAutoSet(document.querySelector("#opponent-select").value,event.target.checked);
const baseLoad=load;
load=async function(season="2025-26"){dataSeason=season;await baseLoad(season);try{let response=await fetch(`data/schedule-${season}.json?t=${Date.now()}`);if(!response.ok)throw Error();let schedule=await response.json();scheduleGames=schedule.games||[];scheduleSeason=schedule.season||""}catch(error){scheduleGames=[];scheduleSeason=""}render()};
async function catchUp(){let button=document.querySelector("#refresh-data"),season=document.querySelector("#season-select").value;button.disabled=true;document.querySelector("#sync-status").textContent=`Catching up ${season} stats…`;try{let response=await fetch(`/api/sync?season=${encodeURIComponent(season)}`,{method:"POST"}),result=await response.json();if(!response.ok||!result.ok)throw Error(result.output||"Local importer failed");await load(season);toast(`${season} data updated.`)}catch(error){console.error(error);document.querySelector("#sync-status").textContent=`Catch-up failed · ${error.message}`;toast("Catch-up failed. See the status message for details.")}finally{button.disabled=false}}
function init(){let now=new Date();document.querySelector("#lineup-date").value=now.toISOString().slice(0,10);activeLineupDate=document.querySelector("#lineup-date").value;let monday=new Date(now);monday.setDate(now.getDate()-(now.getDay()+6)%7);document.querySelector("#week-start").value=monday.toISOString().slice(0,10);document.querySelector("#lineup-date").onchange=e=>{save();activeLineupDate=e.target.value;team().lineup={...(team().lineupsByDate?.[activeLineupDate]||{})};save();render()};document.querySelectorAll(".roster-table thead tr").forEach(row=>{let th=document.createElement("th");th.textContent="EFF";row.insertBefore(th,row.children[6])});let playerHead=document.querySelector(".player-table thead tr"),effHead=document.createElement("th");effHead.textContent="EFF";playerHead.insertBefore(effHead,playerHead.children[3]);bind();document.querySelector("#refresh-data").onclick=catchUp;render();load(document.querySelector("#season-select").value);setInterval(()=>load(document.querySelector("#season-select").value),300000)}
init();
document.querySelector("#reset-roster").onclick=()=>{let current=team();if(!current.playerIds.length)return toast("Roster is already empty.");if(!confirm(`Reset all players on ${current.name}?`))return;current.playerIds=[];current.lineup={};current.lineupsByDate={};save();render();toast("Roster reset.")};

function dateKey(date){return`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`}
function lineupWeekDates(){
  let selected=new Date(`${document.querySelector("#lineup-date").value||new Date().toISOString().slice(0,10)}T12:00:00`);
  selected.setDate(selected.getDate()-(selected.getDay()+6)%7);
  return Array.from({length:7},(_,index)=>{let date=new Date(selected);date.setDate(selected.getDate()+index);return date});
}
function renderWeekSchedule(){
  let dates=lineupWeekDates(),rosterPlayers=roster(team()),list=document.querySelector("#week-schedule-row");
  let start=dates[0],end=dates[6],format=date=>date.toLocaleDateString(undefined,{month:"short",day:"numeric"});
  document.querySelector("#week-schedule-heading").textContent=`${format(start)} – ${format(end)}`;
  document.querySelector("#week-schedule-team").textContent=team().name;
  if(scheduleSeason!==dataSeason){
    document.querySelector("#week-schedule-status").textContent=`${dataSeason} schedule is unavailable. Refresh schedule data to see this week's games.`;
    list.innerHTML="";
    return;
  }
  document.querySelector("#week-schedule-status").textContent=`Games for ${team().name} players · select a lineup date above to change the displayed week.`;
  list.innerHTML=dates.map(date=>{
    let key=dateKey(date),playing=[];
    for(let person of rosterPlayers){
      let projection=gamesForPlayer(person,key);
      for(let game of projection?.games||[]){
        let index=game.teams.indexOf(projection.team),opponent=game.teams[index===0?1:0];
        let activeSlot=slots(team()).find(slot=>slotLabel(slot)!=="BN"&&String(team().lineup?.[slot])===String(person.id));
        playing.push({person,opponent,home:index===1,active:!!activeSlot,slot:activeSlot});
      }
    }
    return`<article class="week-day ${playing.length?"has-games":""}"><div class="week-day-heading"><span>${date.toLocaleDateString(undefined,{weekday:"short"})}</span><time datetime="${key}">${date.getDate()}</time></div><div class="week-day-games">${playing.length?playing.map(game=>`<div class="week-game-player ${game.active?"is-active":"is-bench"}"><strong>${esc(game.person.name)}</strong><span>${game.home?"vs":"@"} ${esc(game.opponent||"NBA")}</span></div>`).join(""):'<span class="week-no-game">No games</span>'}</div><small class="week-game-count">${playing.length?`${playing.length} player${playing.length===1?"":"s"}`:"—"}</small></article>`;
  }).join("");
}
function autoSetLineup(){
  let current=team(),date=document.querySelector("#lineup-date").value;
  if(scheduleSeason!==dataSeason)return toast(`${dataSeason} schedule is unavailable.`);
  let activeSlots=slots(current).filter(slot=>slotLabel(slot)!=="BN"),playersOnRoster=roster(current);
  let scheduled=new Set(playersOnRoster.filter(person=>gamesForPlayer(person,date)?.games.length).map(person=>String(person.id)));
  let ordered=playersOnRoster.sort((a,b)=>{
    let aHasGame=scheduled.has(String(a.id)),bHasGame=scheduled.has(String(b.id));
    if(aHasGame!==bHasGame)return aHasGame?-1:1;
    let aWasActive=activeSlots.some(slot=>String(current.lineup?.[slot])===String(a.id)),bWasActive=activeSlots.some(slot=>String(current.lineup?.[slot])===String(b.id));
    if(aWasActive!==bWasActive)return aWasActive?-1:1;
    let aOptions=activeSlots.filter(slot=>eligible(a,slot)).length,bOptions=activeSlots.filter(slot=>eligible(b,slot)).length;
    return aOptions-bOptions||(a.name||"").localeCompare(b.name||"");
  });
  let assigned={},matchPlayer=(person,seenSlots)=>{
    for(let slot of activeSlots){
      if(seenSlots.has(slot)||!eligible(person,slot))continue;
      seenSlots.add(slot);
      let occupant=assigned[slot]&&player(assigned[slot]);
      if(!occupant||matchPlayer(occupant,seenSlots)){assigned[slot]=person.id;return true}
    }
    return false;
  };
  for(let person of ordered)matchPlayer(person,new Set());
  current.lineup=assigned;
  save();
  render();
  let gamesInLineup=activeSlots.filter(slot=>scheduled.has(String(current.lineup[slot]))).length;
  toast(`Auto-set: ${gamesInLineup} of ${activeSlots.filter(slot=>current.lineup[slot]).length} active players have a game on ${new Date(`${date}T12:00:00`).toLocaleDateString()}.`);
}
document.querySelector("#auto-set-lineup").onclick=autoSetLineup;

let livePlayers=[],liveSeason="",liveLoadSequence=0,selectedLivePlayerId="",rosterPoolPlayers=[];
function liveStat(value,digits=1){let number=Number(value);return Number.isFinite(number)?number.toFixed(digits):"–"}
function liveDate(value){let date=new Date(`${value}T12:00:00`);return Number.isNaN(date.getTime())?esc(value):date.toLocaleDateString(undefined,{month:"short",day:"numeric",year:"numeric"})}
function updateLiveSyncStamp(timestamp){
  let stamp=document.querySelector("#live-sync-stamp");
  if(!timestamp){stamp.textContent="Last sync: Not yet";stamp.removeAttribute("title");return}
  let date=new Date(timestamp);
  if(Number.isNaN(date.getTime())){stamp.textContent="Last sync: unavailable";stamp.removeAttribute("title");return}
  stamp.textContent=`Last sync: ${date.toLocaleString()}`;
  stamp.title=date.toLocaleString(undefined,{dateStyle:"full",timeStyle:"long"});
}
const LIVE_CSV_KEY="hoopsim-live-csv-v1";
function parseCsv(text){
  let rows=[],row=[],cell="",quoted=false;
  for(let index=0;index<text.length;index++){
    let char=text[index];
    if(quoted){
      if(char==='"'&&text[index+1]==='"'){cell+='"';index++}
      else if(char==='"')quoted=false;
      else cell+=char;
    }else if(char==='"'&&!cell)quoted=true;
    else if(char===","){row.push(cell);cell=""}
    else if(char==="\n"||char==="\r"){
      if(char==="\r"&&text[index+1]==="\n")index++;
      row.push(cell);cell="";
      if(row.some(value=>value.trim()))rows.push(row);
      row=[];
    }else cell+=char;
  }
  if(quoted)throw Error("CSV contains an unclosed quoted field.");
  if(cell||row.length){row.push(cell);if(row.some(value=>value.trim()))rows.push(row)}
  if(rows.length<2)throw Error("CSV must include a header and at least one game row.");
  return rows;
}
function csvHeader(value){return String(value||"").replace(/^\uFEFF/,"").trim().toUpperCase().replace(/[^A-Z0-9]/g,"")}
function csvNumber(value,field){
  let raw=String(value??"").trim();
  if(!raw||raw==="–"||raw==="-")return 0;
  if(field==="MIN"&&raw.includes(":")){
    let [minutes,seconds]=raw.split(":");
    let parsedMinutes=Number(minutes),parsedSeconds=Number(seconds);
    if(Number.isFinite(parsedMinutes)&&Number.isFinite(parsedSeconds))return parsedMinutes+parsedSeconds/60;
  }
  let parsed=Number(raw.replace(/,/g,"").replace(/%$/,""));
  if(!Number.isFinite(parsed))throw Error(`Invalid number "${raw}" in ${field}.`);
  if(raw.endsWith("%")||(["FG_PCT","FT_PCT","FG3_PCT"].includes(field)&&Math.abs(parsed)>1))parsed/=100;
  return parsed;
}
function csvDate(value){
  let raw=String(value||"").trim();
  if(/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(raw)){
    let [month,day,year]=raw.split("/");
    return`${year}-${month.padStart(2,"0")}-${day.padStart(2,"0")}`;
  }
  let date=new Date(raw);
  if(Number.isNaN(date.getTime()))throw Error(`Invalid game date "${raw}".`);
  return date.toISOString().slice(0,10);
}
function buildLivePoolFromCsv(text,season){
  let rows=parseCsv(text),headers=rows.shift().map(csvHeader),aliases={
    id:["PLAYERID","PERSONID","ID"],name:["PLAYERNAME","PLAYER","NAME"],team:["TEAMABBREVIATION","TEAM","TEAMCODE"],
    gameId:["GAMEID"],date:["GAMEDATE","DATE"],matchup:["MATCHUP","OPPONENT"],
    FGM:["FGM","FIELDGOALSMADE"],FGA:["FGA","FIELDGOALSATTEMPTED"],FG3M:["FG3M","3PM","THREESMADE"],
    FG3A:["FG3A","3PA","THREESATTEMPTED"],FTM:["FTM","FREETHROWSMADE"],FTA:["FTA","FREETHROWSATTEMPTED"],
    OREB:["OREB","OFFENSIVEREBOUNDS"],DREB:["DREB","DEFENSIVEREBOUNDS"],REB:["REB","REBOUNDS"],
    AST:["AST","ASSISTS"],STL:["STL","STEALS"],BLK:["BLK","BLOCKS"],TOV:["TOV","TO","TURNOVERS"],
    PF:["PF","FOULS"],PTS:["PTS","POINTS"],PLUS_MINUS:["PLUSMINUS","PLUSMINUSPOINTS"],MIN:["MIN","MINUTESPLAYED","MINPLAYED"],
    FG_PCT:["FGPCT","FG","FIELDGOALPERCENTAGE"],FT_PCT:["FTPCT","FT","FREETHROWPERCENTAGE"],FG3_PCT:["FG3PCT","3PPCT","3PTFG","THREEPOINTFGPCT","THREEPOINTPERCENTAGE"],PER:["PER","PLAYEREFFICIENCYRATING"]
  },columns=Object.fromEntries(Object.entries(aliases).map(([key,names])=>[key,headers.findIndex(header=>names.includes(header))]));
  if(columns.name<0||columns.date<0)throw Error("CSV needs player name and game date columns (for example PLAYER_NAME and GAME_DATE).");
  if(!["PTS","FGM","FGA","REB","AST","MIN"].some(key=>columns[key]>=0))throw Error("CSV needs at least one stats column, such as PTS, REB, AST, or MIN.");
  let people=new Map(),games=new Set();
  rows.forEach((cells,index)=>{
    let value=key=>columns[key]>=0?cells[columns[key]]??"": "",name=String(value("name")).trim();
    if(!name)throw Error(`Missing player name on CSV row ${index+2}.`);
    let date;
    try{date=csvDate(value("date"))}catch(error){throw Error(`${error.message} (CSV row ${index+2})`)}
    let team=String(value("team")).trim().toUpperCase(),providedId=String(value("id")).trim(),identity=providedId||name.toLowerCase();
    let person=people.get(identity);
    if(!person){person={id:providedId||`csv-${identity}`,name,team:team||"NBA",gameLogs:[],totals:{},percentageTotals:{FG_PCT:0,FT_PCT:0,FG3_PCT:0},perTotal:0,perCount:0};people.set(identity,person)}
    else if(team)person.team=team;
    let game={gameId:String(value("gameId")).trim(),date,team:team||person.team,matchup:String(value("matchup")).trim()};
    for(let key of ["FGM","FGA","FG3M","FG3A","FTM","FTA","OREB","DREB","REB","AST","STL","BLK","TOV","PF","PTS","PLUS_MINUS","MIN","FG_PCT","FT_PCT","FG3_PCT","PER"]){
      let raw=value(key);
      try{game[key]=csvNumber(raw,key)}catch(error){throw Error(`${error.message} (CSV row ${index+2})`)}
    }
    if(!game.FG_PCT&&game.FGA)game.FG_PCT=game.FGM/game.FGA;
    if(!game.FT_PCT&&game.FTA)game.FT_PCT=game.FTM/game.FTA;
    if(!game.FG3_PCT&&game.FG3A)game.FG3_PCT=game.FG3M/game.FG3A;
    person.gameLogs.push(game);
    for(let key of ["FGM","FGA","FG3M","FG3A","FTM","FTA","OREB","DREB","REB","AST","STL","BLK","TOV","PF","PTS","PLUS_MINUS","MIN"])person.totals[key]=(person.totals[key]||0)+game[key];
    for(let key of ["FG_PCT","FT_PCT","FG3_PCT"])person.percentageTotals[key]+=game[key];
    if(game.PER){person.perTotal+=game.PER;person.perCount++}
    games.add(game.gameId||`${date}|${team}|${game.matchup}|${team||game.matchup?"":"row-"+index}`);
  });
  let players=[...people.values()].map(person=>{
    let totals=person.totals,gp=person.gameLogs.length,stats=Object.fromEntries(Object.entries(totals).map(([key,value])=>[key,Number((value/gp).toFixed(3))]));
    stats.GP=gp;stats.PER=person.perCount?Number((person.perTotal/person.perCount).toFixed(2)):0;
    stats.FG_PCT=totals.FGA?Number((totals.FGM/totals.FGA).toFixed(4)):Number((person.percentageTotals.FG_PCT/gp).toFixed(4));
    stats.FT_PCT=totals.FTA?Number((totals.FTM/totals.FTA).toFixed(4)):Number((person.percentageTotals.FT_PCT/gp).toFixed(4));
    stats.FG3_PCT=totals.FG3A?Number((totals.FG3M/totals.FG3A).toFixed(4)):Number((person.percentageTotals.FG3_PCT/gp).toFixed(4));
    stats.EFF=Number(((totals.PTS+totals.REB+totals.AST+totals.STL+totals.BLK-(totals.FGA-totals.FGM)-(totals.FTA-totals.FTM)-totals.TOV)/gp).toFixed(2));
    return{id:person.id,name:person.name,team:person.team,season,stats,...stats,gameLogs:person.gameLogs};
  }).sort((a,b)=>a.name.localeCompare(b.name));
  return{season,lastSyncedAt:new Date().toISOString(),source:"CSV upload",playerCount:players.length,playerGameLines:rows.length,gameCount:games.size,players};
}
function savedCsvPool(season){
  let uploads=JSON.parse(localStorage.getItem(LIVE_CSV_KEY)||"{}");
  return uploads[season]||null;
}
function updateCsvControls(season){
  document.querySelector("#clear-live-csv").hidden=!savedCsvPool(season);
}
function renderLiveData(){
  let search=document.querySelector("#live-player-search").value.toLowerCase().trim(),select=document.querySelector("#live-player-select");
  let options=livePlayers.filter(p=>(p.name||"").toLowerCase().includes(search)).sort((a,b)=>(a.name||"").localeCompare(b.name||""));
  if(!options.some(p=>String(p.id)===selectedLivePlayerId))selectedLivePlayerId=String(options[0]?.id??"");
  select.innerHTML=options.map(p=>`<option value="${esc(p.id)}">${esc(p.name)} · ${esc(p.team||"NBA")}</option>`).join("");
  select.value=selectedLivePlayerId;
  let current=options.find(p=>String(p.id)===selectedLivePlayerId),rows=document.querySelector("#live-game-rows"),summary=document.querySelector("#live-player-summary"),empty=document.querySelector("#live-game-empty");
  document.querySelector("#live-player-heading").textContent=current?.name||"No player selected";
  if(!current){summary.innerHTML="";rows.innerHTML="";empty.classList.add("visible");return}
  let logs=[...(current.gameLogs||[])].sort((a,b)=>String(b.date).localeCompare(String(a.date)));
  let stats=current.stats||current,latest=logs[0];
  summary.innerHTML=[
    ["GAMES",stats.GP??logs.length,0],
    ["PPG",stats.PTS,1],
    ["RPG",stats.REB,1],
    ["APG",stats.AST,1],
    ["LATEST GAME",latest?liveDate(latest.date):"–",null],
  ].map(([label,value,digits])=>`<div class="live-stat"><span>${label}</span><strong>${digits===null?esc(value):liveStat(value,digits)}</strong></div>`).join("");
  rows.innerHTML=logs.map(game=>`<tr><td>${liveDate(game.date)}</td><td>${esc(game.matchup||game.team||"–")}</td><td>${liveStat(game.MIN)}</td><td>${liveStat(game.PTS,0)}</td><td>${liveStat(game.REB,0)}</td><td>${liveStat(game.AST,0)}</td><td>${liveStat(game.STL,0)}</td><td>${liveStat(game.BLK,0)}</td><td>${liveStat(game.FG3M,0)}</td><td>${liveStat(game.FG_PCT*100)}%</td><td>${liveStat(game.FT_PCT*100)}%</td><td>${liveStat(game.PLUS_MINUS,0)}</td></tr>`).join("");
  empty.classList.toggle("visible",!logs.length);
}
function renderRosterPool(){
  let query=document.querySelector("#roster-pool-search").value.toLowerCase().trim();
  let liveById=new Map((liveSeason==="2026-27"?livePlayers:[]).map(p=>[String(p.id),p]));
  let list=rosterPoolPlayers.filter(p=>`${p.name||""} ${p.team||""}`.toLowerCase().includes(query));
  document.querySelector("#roster-pool-count").textContent=`${list.length} players`;
  document.querySelector("#roster-pool-rows").innerHTML=list.map(person=>{
    let current=liveById.get(String(person.id)),stats=current?.stats?.GP?current.stats:(person.stats||person),games=Number(stats.GP||0);
    let stat=(key,digits=1)=>games&&stats[key]!==undefined?liveStat(stats[key],digits):"–";
    let percent=key=>games&&Number.isFinite(Number(stats[key]))?`${(Number(stats[key])*100).toFixed(1)}%`:"–";
    return`<tr><td class="roster-pool-name">${esc(person.name)}</td><td>${esc(person.team||"–")}</td><td>${stat("MIN")}</td><td>${percent("FG_PCT")}</td><td>${percent("FT_PCT")}</td><td>${percent("FG3_PCT")}</td><td>${stat("PTS")}</td><td>${stat("REB")}</td><td>${stat("AST")}</td><td>${stat("STL")}</td><td>${stat("BLK")}</td><td>${stat("TOV")}</td><td>${games&&stats.PER!==undefined?liveStat(stats.PER):"–"}</td></tr>`;
  }).join("");
  document.querySelector("#roster-pool-empty").classList.toggle("visible",!list.length);
}
async function loadRosterPool(){
  let status=document.querySelector("#roster-pool-status");
  status.textContent="Loading 2026–27 active roster and draft class…";
  try{
    let [poolResponse,draftResponse]=await Promise.all([
      fetch(`data/players-2026-27.json?t=${Date.now()}`),
      fetch(`data/draft-2026.json?t=${Date.now()}`),
    ]);
    if(!poolResponse.ok)throw Error(`2026–27 player pool request failed (${poolResponse.status}).`);
    if(!draftResponse.ok)throw Error(`2026 draft class request failed (${draftResponse.status}).`);
    let [pool,draft]=await Promise.all([poolResponse.json(),draftResponse.json()]);
    let active=(pool.players||[]).filter(p=>p.rosterSeason==="2026-27"),byId=new Map(active.map(p=>[String(p.id),p]));
    for(let rookie of draft.players||[]){
      let id=String(rookie.id),existing=byId.get(id);
      if(existing){if(!existing.team||existing.team==="FA")existing.team=rookie.team||"Rookie";continue}
      byId.set(id,{...rookie,team:rookie.team||"Rookie",season:"2026-27",stats:rookie.stats||{}});
    }
    rosterPoolPlayers=[...byId.values()].sort((a,b)=>(a.name||"").localeCompare(b.name||""));
    status.textContent=`${rosterPoolPlayers.length.toLocaleString()} active roster players and rookies · 2026–27 season.`;
  }catch(error){
    console.error(error);
    rosterPoolPlayers=[];
    status.textContent=`Could not load the 2026–27 roster pool: ${error.message}`;
  }
  renderRosterPool();
}
async function loadLiveData(season){
  let sequence=++liveLoadSequence;
  document.querySelector("#live-data-status").textContent=`Loading ${season} completed game logs…`;
  try{
    let uploaded=savedCsvPool(season);
    if(uploaded){
      livePlayers=uploaded.players||[];
      liveSeason=season;
      updateLiveSyncStamp(uploaded.lastSyncedAt);
      document.querySelector("#live-data-status").textContent=`${livePlayers.length.toLocaleString()} players · ${Number(uploaded.gameCount||0).toLocaleString()} games · imported from CSV ${new Date(uploaded.lastSyncedAt).toLocaleString()}. This browser's CSV data is active.`;
    }else{
      let response=await fetch(`data/live-players-${season}.json?t=${Date.now()}`);
      if(sequence!==liveLoadSequence)return;
      if(response.status===404){livePlayers=[];liveSeason=season;updateLiveSyncStamp(null);document.querySelector("#live-data-status").textContent=`No ${season} game logs synced yet. Update live stats or upload a game-log CSV.`}
      else if(!response.ok)throw Error(`Live game-log request failed (${response.status}).`);
      else{
        let pool=await response.json();
        if(sequence!==liveLoadSequence)return;
        livePlayers=pool.players||[];
        liveSeason=season;
        updateLiveSyncStamp(pool.lastSyncedAt);
        let synced=pool.lastSyncedAt?new Date(pool.lastSyncedAt).toLocaleString():"sync time unavailable";
        document.querySelector("#live-data-status").textContent=`${livePlayers.length.toLocaleString()} players · ${Number(pool.gameCount||0).toLocaleString()} games · synced ${synced}. Completed box scores update after games finish.`;
      }
    }
    updateCsvControls(season);
  }catch(error){
    if(sequence!==liveLoadSequence)return;
    console.error(error);
    livePlayers=[];
    liveSeason=season;
    document.querySelector("#clear-live-csv").hidden=true;
    updateLiveSyncStamp(null);
    document.querySelector("#live-data-status").textContent=`Could not load ${season} game logs: ${error.message}`;
  }
  renderLiveData();
  renderRosterPool();
}
async function syncLiveData(){
  let button=document.querySelector("#sync-live-data"),season=document.querySelector("#season-select").value;
  if(savedCsvPool(season)){toast("CSV data is active. Choose Use synced data before fetching from the server.");return}
  button.disabled=true;
  updateLiveSyncStamp(null);
  document.querySelector("#live-sync-stamp").textContent="Last sync: Updating…";
  document.querySelector("#live-data-status").textContent=`Fetching completed ${season} player game logs…`;
  try{
    let response=await fetch(`/api/live-sync?season=${encodeURIComponent(season)}`,{method:"POST"}),result=await response.json();
    if(!response.ok||!result.ok)throw Error(result.output||"Live game-log sync failed.");
    await loadLiveData(season);
    toast(`${season} live game stats updated.`);
  }catch(error){
    console.error(error);
    document.querySelector("#live-sync-stamp").textContent="Last sync: Update failed";
    document.querySelector("#live-data-status").textContent=`Live stats update failed: ${error.message}`;
    toast("Live stats update failed. See the status message for details.");
  }finally{button.disabled=false}
}
const scheduledLoad=load;
load=async function(season="2025-26"){
  await scheduledLoad(season);
  await Promise.all([loadLiveData(season),loadRosterPool()]);
};
document.querySelector("#live-player-search").oninput=renderLiveData;
document.querySelector("#live-player-select").onchange=event=>{selectedLivePlayerId=event.target.value;renderLiveData()};
document.querySelector("#sync-live-data").onclick=syncLiveData;
document.querySelector("#upload-live-csv").onclick=()=>document.querySelector("#live-csv-file").click();
document.querySelector("#live-csv-file").onchange=async event=>{
  let file=event.target.files?.[0];
  event.target.value="";
  if(!file)return;
  let season=document.querySelector("#season-select").value;
  try{
    if(!file.name.toLowerCase().endsWith(".csv"))throw Error("Choose a .csv file.");
    let pool=buildLivePoolFromCsv(await file.text(),season),uploads=JSON.parse(localStorage.getItem(LIVE_CSV_KEY)||"{}");
    uploads[season]=pool;
    localStorage.setItem(LIVE_CSV_KEY,JSON.stringify(uploads));
    selectedLivePlayerId="";
    await loadLiveData(season);
    toast(`Imported ${pool.playerGameLines.toLocaleString()} player game rows from CSV.`);
  }catch(error){
    console.error(error);
    document.querySelector("#live-data-status").textContent=`CSV upload failed: ${error.message}`;
    toast("CSV upload failed. Check the status message.");
  }
};
document.querySelector("#clear-live-csv").onclick=()=>{
  let season=document.querySelector("#season-select").value;
  try{
    let uploads=JSON.parse(localStorage.getItem(LIVE_CSV_KEY)||"{}");
    delete uploads[season];
    localStorage.setItem(LIVE_CSV_KEY,JSON.stringify(uploads));
    selectedLivePlayerId="";
    loadLiveData(season);
  }catch(error){
    console.error(error);
    document.querySelector("#live-data-status").textContent=`Could not remove the uploaded CSV: ${error.message}`;
  }
};
document.querySelector("#roster-pool-search").oninput=renderRosterPool;
Promise.all([loadLiveData(document.querySelector("#season-select").value),loadRosterPool()]);
