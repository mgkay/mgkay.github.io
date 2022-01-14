%% Routing 3: Vehicle Routing

%% Example 1. TSP: Unconstrained cyclic route
% Dataset of 30 NC Shipments (with 54 different begin-end locations)
clear
load shmtNC30
%% Add depot: Use end location of shipment 1 as depot for all shipments
XY = XY([e(1); b],:);
D = dists(XY,XY,'mi')*1.2;
sh = vec2struct('b',1,'e',2:size(XY,1));
tr = struct('b',1,'e',1);
sdisp(sh)
%% Construct & improve routes:
rTDh = @(rte) rteTC(rte,sh,D,tr);
ph = @(rte) plotshmt(sh,XY,rte,tr);
IJS = pairwisesavings(rTDh,sh);
[r1,TD1] = twoopt(savings(rTDh,sh,IJS,ph),rTDh,ph);
pplot(XY(1,:),'ks')
plotshmt(sh,XY,r1,tr)
%% Use TSP procedure:
[loc,TD1,bestvtx] = tspnneighbor(D)
[loc,TD1] = tsp2opt(loc,D)

%% Example 2. VRP: Ex 1 + Add customer demands and truck capacity
sh = vec2struct('b',1,'e',2:size(XY,1));
sh = vec2struct(sh,'q',q,'s',s);
tr = vec2struct(tr,'Kwt',25,'Kcu',2750)
sdisp(sh)
%% Construct & improve routes:
rTDh = @(rte) rteTC(rte,sh,D,tr);
ph = @(rte) plotshmt(sh,XY,rte,tr);
IJS = pairwisesavings(rTDh,sh);
[r2,TD2] = twoopt(savings(rTDh,sh,IJS,ph),rTDh,ph);
pplot(XY(1,:),'ks')
plotshmt(sh,XY,r2,tr)
%% Route weight and cube
Wt = cellfun(@(r)sum(q(rte2idx(r))),r2);
cu = 2000*q./s;
Cube = cellfun(@(r)sum(cu(rte2idx(r))),r2);
vdisp('TD2,Wt,Cube')
%% FYI: Convert route to shipment index vector
help rte2idx
rte = [23   15   6   23   27   17   24   27   15   17   6   24];
rte2idx(rte)
isorigin(rte)
rte(isorigin(rte))

%% Example 3. VRP: Ex 2 + Add max route distance constraint
rTDh0 = @(rte) rteTC(rte,sh,D,tr);
maxdist = 600;
%% Construct & improve routes:
rTDh = @(rte) myrteTC(rte,rTDh0,maxdist);
ph = @(rte) plotshmt(sh,XY,rte,tr);
IJS = pairwisesavings(rTDh,sh);
[r3,TD3] = twoopt(savings(rTDh,sh,IJS,ph),rTDh,ph);
pplot(XY(1,:),'ks')
plotshmt(sh,XY,r3,tr)
%% Route weight and cube
Wt = cellfun(@(r)sum(q(rte2idx(r))),r3);
cu = 2000*q./s;
Cube = cellfun(@(r)sum(cu(rte2idx(r))),r3);
vdisp('TD3,Wt,Cube')

%% Example 4. VRP: Ex 2 + Use built-in max TC (no plotting)
tr = setfield(tr,'maxTC',600);
%% Construct & improve routes:
rTDh = @(rte) rteTC(rte,sh,D,tr);
IJS = pairwisesavings(rTDh,sh);
[r4,TD4] = twoopt(savings(rTDh,sh,IJS),rTDh);
%% Route weight and cube
Wt = cellfun(@(r)sum(q(rte2idx(r))),r4);
cu = 2000*q./s;
Cube = cellfun(@(r)sum(cu(rte2idx(r))),r4);
vdisp('TD4,Wt,Cube')

%% Example 5. Time window example from slide
T5 = zeros(4);
T5(1,2) = 1; T5(2,3) = 2; T5(3,4) = 1; T5(4,1) = 1; mdisp(T5)
sh5 = vec2struct('b',1,'e',[2 3 4]);
sh5 = vec2struct(sh5,'tU',0,'temin',[8 12 15],'temax',[11 14 18]);
tr5 = struct('b',1,'e',1,'tbmin',6,'tbmax',18,'temin',18,'temax',24)
sdisp(sh5)
%% Determine route cost/feasibility and display route output structure
[TC5,Xflg5,out5] = rteTC([1 2 3 1 2 3],sh5,T5,tr5);
TC5,Xflg5
sdisp(out5,false)

%% Example 6. VRP: Ex 2 + Minimize travel time with time window contraints
T = D/50;       % 50 mph average travel speed
T = T + 5/60;   % 5 min positioning time at each stop
tU = q * 30/60; % 30 min/ton unloading time (ignore loading time at depot
% Two types of time windows: [7 17} daytime delivery and [13 23] evening
temin = [repmat(7,1,15) repmat(13,1,15)];  % Cust 1-15 daytime delivery
temax = [repmat(17,1,15) repmat(23,1,15)]; % Cust 16-30 evening delivery
sh = vec2struct('b',1,'e',2:size(XY,1));
sh = vec2struct(sh,'q',q,'s',s);
sh = vec2struct(sh,'tU',tU,'temin',temin,'temax',temax);
tr = struct('b',1,'e',1,'Kwt',25,'Kcu',2750);
sdisp(sh)
%% Construct & improve routes:
rTDh = @(rte) rteTC(rte,sh,T,tr);
ph = @(rte) plotshmt(sh,XY,rte,tr);
IJS = pairwisesavings(rTDh,sh);
r6 = twoopt(savings(rTDh,sh,IJS,ph),rTDh,ph);
pplot(XY(1,:),'ks')
plotshmt(sh,XY,r6,tr)
%% Display route output structure
[TC6,Xflg6,out6] = rTDh(r6);
for i = 1:length(out6), sdisp(out6(i),false,i), end
