% Freight Transport 3: Transshipment and Total Logistics Cost

%% Example A: Location and Freight Transport
%% Two suppliers distribute products through DC to three customers
uwt = [30 120];         % unit weight (lb)
ucu = [10 4];           % unit cube (ft^3)
fS = [100 380];         % annual demand (ton/yr)
shS = vec2struct('f',fS,'s',uwt./ucu);
pct = [20 30 50]/100;  % customer demand percentage
sh = aggshmt(shS);
sh = [shS vec2struct(sh,'f',sh.f*pct)];
sdisp(sh) 
tr = struct('r',2,'Kwt',25,'Kcu',2750)
qmax = maxpayld(sh,tr)
Sx = [50; 150];        % suppliers in Asheville and Stateville
Cx = [190; 270; 420];  % customers in Winston-Salem, Durham, Wilmington
%% FTL: Locate DC to min transport cost assuming FTL used for all transport
n = ([sh.f]./qmax);    % shipment frequency
w = n*tr.r;            % monetary weight ($/mi)
DCtc = minisumloc([Sx; Cx],w,1)
TCh = @(x) sum(w(:)'.*dists(x,[Sx; Cx],1));
DCtc = fminsearch(TCh,mean([Sx; Cx]))
%% FTL: Monthly outbound frequency constraint
nmin = 12;             % outbound frequency constraint
n12 = [n(1:2) max(n(3:end),nmin)];
w12 = n12*tr.r;
DCtc = minisumloc([Sx; Cx],w12,1)
%% TLC: Locate DC to min TLC
uval = [300 450];      % unit value ($)
a = 0.5;               % alpha batch prod, uncoord DC, constant consumption 
shS = vec2struct(shS,'a',a,'v',uval./(uwt/2000),'h',.3);
sh = aggshmt(shS);
sh = [shS vec2struct(sh,'f',sh.f*pct)];
sdisp(sh)
                       % add 'd' to sh based on location x
shd_h = @(x) vec2struct(sh,'d',[dists(Sx,x,1)' dists(x,Cx,1)]*1.2);
%% TLC with FTL: Assume FTL still used for all transport
TLCftl_h = @(x) sum(totlogcost(qmax,transcharge(qmax,shd_h(x),tr),sh));
DCtc, TLCtc = TLCftl_h(DCtc)                            % use min TC loc
[DCftl,TLCftl] = fminsearch(TLCftl_h,randX([Sx; Cx],1)) % find min location
plot(arrayfun(TLCftl_h,[0:1:350]),'r'), shg, hold on    % plot TLC for FTL
%% TLC with TL: Use shipment size corresponding to min TLC
TLCh = @(x) sum(minTLC(shd_h(x),tr));                   % TLC optimal TL
[DCtlc,TLCtlc] = fminsearch(TLCh,randX([Sx; Cx],1))     % find min location   
plot(arrayfun(TLCh,[0:1:350]),'b'), shg, hold off       % plot TLC for TL
%% TLC at Statesville
TLCh(150)                             % can't find due to MC in transcharge
[DCtlc,TLCtlc] = fminsearch(TLCh,150)
TLCftl/TLCtlc

%% Example B: Direct vs. Transshipment
%% Determine supplier (S) and customer (C) locations
city2lonlat = @(city,st) ...
   uscity('XY',mand(city,uscity('Name'),st,uscity('ST')));
Ccity = {'Portland','Tucson','Denver','Milwaukee'};
Cst = {'OR','AZ','CO','WI'};
CXY = city2lonlat(Ccity,Cst);
Scity = {'Rochester','Orlando','San Antonio'};
Sst = {'NY','FL','TX'};
SXY = city2lonlat(Scity,Sst);
%% Data: 3 Different Products Supplied to 4 Customers
ppiTL = 131.4; % Jan 2018 (P)
ppiLTL = 179.4; % Jan 2018 (P)
tr = struct('r',2*(ppiTL/102.7),'Kwt',25,'Kcu',2750);
sS = [32 3 12];            % density (lb/ft^3) 
fS = [500 75 300];         % demand (ton/yr)
aS = 0;                    % alpha for batch production at suppliers
aC = 0.5;                  % alpha for constant consumption at customers
pct = [20 35 25 20]/100;   % customer demand percentage
v = [50000 25000 10000];   % product cost ($/ton)
%% 1: Direct Shipments
%% Create shipments
F = fS(:)*pct
S = repmat(sS(:),1,size(CXY,1));
V = repmat(v(:),1,size(CXY,1));
D = dists(SXY,CXY,'mi')*1.2;
sh = vec2struct('f',F(:),'s',S(:),'a',aS+aC,'v',V(:),'h',.3,'d',D(:));
sdisp(sh)
%% Determine optimal shipment sizes
[TLC1,q1,isLTL1] = minTLC(sh,tr,ppiLTL);
qmax1 = maxpayld(sh,tr);
n1 = [sh.f]./q1;
t1 = 365.25./n1;
vdisp('TLC1,q1,qmax1,n1,t1,isLTL1',true,true)
%% 2: Use a DC with No Coordination
%% Use existing DC
DCcity = 'Memphis';
DC = city2lonlat(DCcity,'TN');
%% Plot
XY = [SXY; DC; CXY];
makemap(XY)
hS = pplot(SXY,'ro');
hDC = pplot(DC,'rv');
hC = pplot(CXY,'r.');
pplot(SXY,Scity)
pplot(DC,{DCcity})
pplot(CXY,Ccity)
legend([hS hDC hC],{'Suppliers','DC','Customers'})
%% Create shipments inbound and outbound to the DC
aO = aS+0.5;           % inbound alpha for no coordination   
aD = 0 + aC;           % outbound alpha for no coordination
shS = vec2struct(...
   'f',fS,'s',sS,'a',aO,'v',v,'h',0.3,'d',dists(SXY,DC,'mi')*1.2);
shC = vec2struct(...
   aggshmt(shS),'f',sum(fS)*pct,'a',aD,'d',dists(DC,CXY,'mi')*1.2);
sh = [shS shC];
qmax = maxpayld(sh,tr);
sdisp(sh)
%% Determine optimal shipment sizes
[TLC2,q2,isLTL2] = minTLC(sh,tr,ppiLTL);
n2 = [sh.f]./q2;
t2 = 365.25./n2;
vdisp('TLC2,q2,qmax,n2,t2,isLTL2',true,true)
%% 3: Use a DC with Perfect Cross-Docking
%% Determine optimal common shipment interval
[shS.a] = deal(aS+0);  % inbound alpha for perfect cross-docking
sh = [shS shC];
TLC30h = @(t) totlogcost([sh.f]*t,transcharge([sh.f]*t,sh,tr,ppiLTL),sh);
TLC3h = @(t) iff([sh.f]*t <= qmax, TLC30h(t), Inf);
tx0 = min(qmax./[sh.f]);
t3 = fminsearch(@(t) sum(TLC3h(t)),tx0)
%% Report results
q3 = [sh.f]*t3;
[~,isLTL3] = transcharge(q3,sh,tr,ppiLTL);
TLC3 = TLC3h(t3);
n3 = [sh.f]./q3;
t3 = 365.25./n3;
vdisp('TLC3,q3,qmax,n3,t3,isLTL3',true,true)
%% 4: Determine initial DC location using FTL approximation
% Use shipment frequency as weights since transport rates identical
w = [sh.f]./qmax
DCftl = minisumloc([SXY; CXY],w,'mi')
[~,~,~,dstr] = lonlat2city(DCftl); disp(dstr)
%% 5: Optimal DC Location with No Cooridination
%% Determine optimal shipment size as subroutine in location procedure
[shS.a] = deal(0.5); sh = [shS shC];
shd_h = @(xy) vec2struct(sh,'d',[dists(SXY,[xy(1) xy(2)],'mi')'*1.2 ...
   dists([xy(1) xy(2)],CXY,'mi')*1.2]);
TLC5h = @(xy) sum(minTLC(shd_h(xy),tr,ppiLTL));
[DC5,TLC5] = fminsearch(TLC5h,DCftl)
[~,~,~,dstr] = lonlat2city(DC5); disp(dstr)
%% Report results
[TLC5,q5,isLTL5] = minTLC(shd_h(DC5),tr,ppiLTL);
n5 = [sh.f]./q5;
t5 = 365.25./n5;
vdisp('TLC5,q5,qmax,n5,t5,isLTL5',true,true)
%% 6: Optimal DC Location with Perfect Cross-Docking
%% Determine optimal common shipment interval along with location (3-D)
[shS.a] = deal(0);   % set inbound alpha to 0
sh = [shS shC];
shd_h = @(xy) vec2struct(sh,'d',[dists(SXY,[xy(1) xy(2)],'mi')' ...
   dists([xy(1) xy(2)],CXY,'mi')]*1.2);
TLC60h = @(xyt) totlogcost([sh.f]*xyt(3),...
   transcharge([sh.f]*xyt(3),shd_h(xyt(1:2)),tr,ppiLTL),shd_h(xyt(1:2)));
TLC6h = @(xyt) iff([sh.f]*xyt(3) <= qmax, TLC60h(xyt), Inf);
tx0 = min(qmax./[sh.f]);
[xyt6,TLC6] = fminsearch(@(xyt) sum(TLC6h(xyt)),[DCftl tx0])
[~,~,~,dstr] = lonlat2city(xyt6(1:2)); disp(dstr)
%% Report results
t6 = xyt6(3);
q6 = [sh.f]*t6;
[~,isLTL6] = transcharge(q6,shd_h(xyt6(1:2)),tr,ppiLTL);
TLC6 = TLC6h(xyt6);
n6 = [sh.f]./q6;
t6 = 365.25./n6;
vdisp('TLC6,q6,qmax,n6,t6,isLTL6',true,true)
%% Report All Results
TLC = cellfun(@sum,{TLC1,TLC2,TLC3,TLC5,TLC6})';
t = cellfun(@mean,{t1,t2,t3,t5,t6})';
LTL = cellfun(@sum,{isLTL1,isLTL2,isLTL3,isLTL5,isLTL6})';
str = {'Uncooridinated','Cross-Docking'};
str = cellfun(@(x) [x ' at ' DCcity],str,'UniformOutput',false);
str = {'Direct',str{:},'Uncooridinated at Optimal Location',...
   'Cross-Docking at Optimal Location'};
mdisp([TLC t LTL],str,{'TLC','t','LTL'},'Transshipment Example')

%% Example C: Optimal Number DCs for Lowe's
%% Data                % Stores at 3-digit zips with populations > 100,000
[CXY,pop] = uszip3('XY','Pop',...
   ~mor({'AK','HI','PR'},uszip3('ST')) & uszip3('Pop') > 100000);
SXY = CXY;             % Different supplier at each 3-digit zip
COGS = 44.04e9         % 2017 Cost of Goods Sold (Lowe's Annual Report)
v = 7000               % Average value for LTL shipment
f = COGS/v             % Annual demand (ton)
s = 10                 % Average density Class 100 product (lb/ft^3)
a = 0.5                % Batch prod., uncoordinated DC, const. consumption
h = 0.3                % Average mfg prod carrying rate
ppiTL = 131.4;         % Jan 2018 (P)
%% Create allocation handle for ALA and IC handle
tr = struct('r',2*(ppiTL/102.7),'Kwt',25,'Kcu',2750)
qmax = maxpayld(s,tr)    % Shipment size, since FTL used for all transport
fC = f*(pop/sum(pop));   % Demand proportional to population
fS = repmat(f./size(SXY,1),size(SXY,1),1);     % Equal allocaton of supply
DCh = @(XY) dists(XY,CXY,'mi')*1.2;            % No area adjustment
FC = @(XY) sparse(argmin(DCh(XY),1),1:length(fC),fC,size(XY,1),length(fC));
FS = @(XY) (sum(FC(XY),2)/sum(fC)) * fS(:)';   % Supplier serve all DCs
W = @(XY) [FS(XY) FC(XY)]*(tr.r/qmax);         % wij = fij * rFTL
TCh = @(XY) sum(sum(W(XY).*[dists(SXY,XY,'mi')'*1.2 DCh(XY)]));  % TC = W*D
alloc_h = @(XY) deal(W(XY),TCh(XY));           % W and TC required outputs
                                               % IC: Supplier-DC + DC-Store
ICh = @(XY) a*v*h*qmax*(prod(size(FS(XY))) + length(fC));  
%% Solve using ALA
nmax = 20;
rng(9348567)
clear TLCn TCn ICn
TLC = Inf;
fprintf('  n  TC         IC         TLC\n');
for n = 1:nmax
   nruns = 5;
   TLCn(n) = Inf;
   for i = 1:nruns
      [XYi,TCi,Wi] = ala(randX(CXY,n),alloc_h,[SXY; CXY],'mi');
      ICi = ICh(XYi);
      TLCi = TCi + ICi;
      if TLCi < TLCn(n), TLCn(n) = TLCi; TCn(n) = TCi; ICn(n) = ICi; end
      if TLCi < TLC, TLC = TLCi; TC = TCi; IC = ICi; XY = XYi; W = Wi; end
   end
   fprintf('%3d %.4e %.4e %.4e\n',n,TCn(n),ICn(n),TLCn(n));
end
lonlat2city(XY)
TLCn(15)/TLCn(9)   % Increase from 9 (opr) to 15 (Lowe's actual) no. of DCs
%% Plot Results
plot([TLCn; TCn; ICn]'), shg, hold on
legend({'TLC','TC','IC'})
plot(find(TLC==TLCn),[TLC TC IC],'ro'), shg, hold off
xlabel('Number of DCs')
ylabel('TLC ($/yr)')
title('Logistics Network Design using TLC: Lowe''s Example')
