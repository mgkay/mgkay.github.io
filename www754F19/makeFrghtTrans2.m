% Freight Transport 2: Periodic Truck Shipments

%% Truck Shipment Example: Periodic
%% Use data from Questions 1-7 for one-time shipment example
sh.d = 532;
uwt = 40; ucu = 9;
sh.s = uwt/ucu
tr.Kwt = 25; tr.Kcu = 2750;
ppiTL = 131.4; % Jan 2018 (P)
ppiLTL = 179.4; % Jan 2018 (P)
tr.r = 2 * (ppiTL/102.7)
qmax = maxpayld(sh,tr)
%% Question 11
sh.f = 20;
n = sh.f/qmax
%% Question 12
t = qmax/sh.f, t = 1/n
days = t * 365.25
%% Question 13
rFTL = tr.r/qmax
TC_FTL = sh.f*rFTL*sh.d
TC_FTL = n*tr.r*sh.d
TC_FTL = n*transcharge(qmax,sh,tr)
tmax = 3/12
rFTL3 = tr.r/min(sh.f*tmax,qmax)
TC_FTL3 = sh.f*rFTL3*sh.d
nmin = 1/tmax
TC_FTL3 = max(n,nmin)*tr.r*sh.d
%% Question 14
sh = vec2struct(sh,'a',1,'v',25000,'h',.3)
IC_FTL = sh.a*sh.v*sh.h * qmax
%% Question 15
TLC_FTL = TC_FTL + IC_FTL
[TLC_FTL,TC_FTL,IC_FTL] = totlogcost(qmax,transcharge(qmax,sh,tr),sh)
%% Question 16
qTL = sqrt((sh.f*tr.r*sh.d)/(sh.a*sh.v*sh.h))
[TLC_TL,qTL] = minTLC(sh,tr)
[TLC_TL,TC,IC] = totlogcost(qTL,transcharge(qTL,sh,tr),sh)
qTL = fminsearch(@(q) totlogcost(q,transcharge(q,sh,tr),sh),qmax)
%% TLC as allocated full-truckload
TC_AllocFTL = sh.f*(tr.r/qmax)*sh.d;
IC_AllocFTL = sh.a*sh.v*sh.h*qTL;
TLC_AllocFTL = TC_AllocFTL + IC_AllocFTL;
vdisp('TC_AllocFTL,IC_AllocFTL,TLC_AllocFTL')
%% Question 17
[TLC_LTL,qLTL] = minTLC(sh,[],ppiLTL);
[TLC,TC,IC] = totlogcost(qLTL,transcharge(qLTL,sh,[],ppiLTL),sh);
vdisp('TLC,qLTL,TC,IC,365.25*qLTL./sh.f')
%% Side issue: Must be careful in picking starting point for optimization
TLCfh = @(q) totlogcost(q,transcharge(q,sh,[],ppiLTL),sh);
q0 = qmax       % qmax > 5 tons
[qLTL,TLC_LTL] = fminsearch(TLCfh,q0)
q0 = qTL
[qLTL,TLC_LTL] = fminsearch(TLCfh,q0)
2000*qTL/sh.s   % > 650 ft^3
q0 = 0          % < 150 lb
[qLTL,TLC_LTL] = fminsearch(TLCfh,q0)
qUB = 650*sh.s/2000
qLB = 150/2000
q0 = geomean([qLB qUB]) % Make starting point feasible
qLTL = fminsearch(TLCfh,q0)
%% Question 18
[TLC,q,isLTL] = minTLC(sh,tr,ppiLTL)
c0 = transcharge(q,sh,tr,ppiLTL)
[TLC,TC,IC] = totlogcost(q,c0,sh)
vdisp('TLC,q,c0,isLTL,TC,IC,365.25*q./sh.f')
%% plot
TLCfh = @(q) log(totlogcost(q,transcharge(q,sh,tr,ppiLTL),sh));
fplot(TLCfh,[150/2000 qmax]), shg
%% Question 19
sh.v = 85000
[TLC,q,isLTL] = minTLC(sh,tr,ppiLTL)
c0 = transcharge(q,sh,tr,ppiLTL)
[TLC,TC,IC] = totlogcost(q,c0,sh)
vdisp('TLC,q,c0,isLTL,TC,IC,365.25*q./sh.f')
%% plot
TLCfh = @(q) log(totlogcost(q,transcharge(q,sh,tr,ppiLTL),sh));
fplot(TLCfh,[150/2000 qTL]), shg
%% Second Product
%% Question 20
sh(2) = vec2struct(sh(1),'f',80,'s',32.16,'v',5000);
sdisp(sh)
[TLC,q,isLTL] = minTLC(sh,tr,ppiLTL)
t = 365.25*q./[sh.f]
vdisp('TLC,q,isLTL,365.25*q./[sh.f]',true)
%% Aggregate Shipment
%% Question 21
ash = aggshmt(sh);
sdisp([sh ash],[],'sh12,agg3')
[TLCa,qa,isLTL] = minTLC(ash,tr)
vdisp('TLCa,qa,365.25*qa/ash.f')
%% Display Summary
qmax = maxpayld(sh,tr)
qmax = maxpayld(ash,tr)
M = [[sh.f] NaN; [sh.s] NaN; [sh.v] NaN; maxpayld(sh,tr) NaN; ...
   TLC sum(TLC); q NaN; t NaN]';
Ma = [ash.f ash.s ash.v maxpayld(ash,tr) TLCa qa 365.25*qa./ash.f'];
mdisp([M; Ma],{'1','2','1+2','Aggregate'},...
   {'f','s','v','qmax','TLC','q','t'},'sh')

