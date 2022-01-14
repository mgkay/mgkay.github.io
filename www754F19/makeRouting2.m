%% Routing 2: Route-based Construction/Improvement Procedures

%% Example 1: Independent vs Consolidated Multi-Stop Shipments
%% Create Shipments
City = {'Raleigh','Athens','Asheville','Jacksonville',...
   'Savannah','Gainesville'};
ST = {'NC','GA','NC','FL','GA','FL'};
XY = uscity('XY',mand(City,uscity('Name'),ST,uscity('ST')));

D = dists(XY,XY,'mi')*1.2;
mdisp(D,City,City)

sh = vec2struct('s',[10 15 7],'b',[1 3 5],'e',[2 4 6]);
sh = vec2struct(sh,'d',diag(D([sh.b],[sh.e])));
sdisp(sh,true)
%% Independent Shipments
TD = sum([sh.d])
help plotshmt
plotshmt(sh,XY)
pplot(XY,City)
set(findobj(gca,'DisplayName','Route Label'),'FontSize',8),shg
%% Route vs location vector
r = [1 1]
sdisp(sh,true)
loc = rte2loc(r,sh)
d = diag(D(loc(1),loc(2)))
r = [1 2 2 1]
loc = rte2loc(r,sh)
d = diag(D(loc(1:end-1),loc(2:end)))
d = loccost(loc,D)
d = sum(d)
d = rteTC(r,sh,D)
%% Consolidated multi-stop shipments
rTDh = @(rte) rteTC(rte,sh,D);
d = rTDh([1 1])
d = rTDh({[1 1],[2 2],[3 3]});  mdisp(d),vdisp('sum(d)')
d = rTDh({[1 1 2 2],[3 3]});    mdisp(d),vdisp('sum(d)')
d = rTDh({[1 2 2 1],[3 3]});    mdisp(d),vdisp('sum(d)')
d = rTDh({[1 2 1 2],[3 3]});    mdisp(d),vdisp('sum(d)')
d = rTDh([1 2 3 1 2 3])
%% Min cost insertion procedure
help mincostinsert
% insert shmt 2 route into shmt 1 route
[r12,TD12] = mincostinsert([2 2],[1 1],rTDh,sh)
% insert shmt 3 route into shmt 1&2 route
[r123,TD123] = mincostinsert([3 3],r12,rTDh,sh)
plotshmt(sh,XY,r123)
pplot(XY,City)
set(findobj(gca,'DisplayName','Route Label'),'FontSize',8),shg
%% Pairwise savings
s12 = sh(1).d + sh(2).d - rTDh(r12)
help pairwisesavings
[IJS,S] = pairwisesavings(rTDh,sh,[sh.d]);
mdisp(S)
mdisp(IJS)
%% Route construction: Savings method
help savings
[rsav,TDsav] = savings(rTDh,sh,IJS,true)

%% Example 2: 8-city TSP
%% Data
clear, close all
vrpnc1
XY = XY(1:8,:);
D = dists(XY,XY,2);
n = size(XY,1)-1;

sh = vec2struct('b',2:n+1,'e',1); sdisp(sh)
sh = fliplr(sh); sdisp(sh)
tr = struct('b',1,'e',1);

rTDh = @(rte) rteTC(rte,sh,D,tr);
%% Route construction: mincostinsert
r1 = [1 1];
for i = 2:length(sh)
   r1 = mincostinsert([i i],r1,rTDh,sh);
end
r1
rte2loc(r1,sh)
TD1 = rTDh(r1)
plotshmt(sh,XY,r1,tr,false)
pplot(XY,num2cell(1:n+1))
%% Route improvement: twoopt
help twoopt   % cf. tsp2opt
[r2,TD2] = twoopt(r1,rTDh);
TD2
plotshmt(sh,XY,r2,tr,false)
pplot(XY,num2cell(1:n+1))
%% Insertimprove: mincostinsert + twoopt for each shmt
help insertimprove
type insertimprove
idxsh = 1:length(sh)
[r3,TD3] = insertimprove(idxsh,rTDh,sh)
rng(392987)
idxsh = randperm(length(sh))
[r3,TD3] = insertimprove(idxsh,rTDh,sh)
%% Route construction: savings
IJS = pairwisesavings(rTDh,sh);
[r4,TD4] = savings(rTDh,sh,IJS)
plotshmt(sh,XY,r4,tr,false)
pplot(XY,num2cell(1:n+1))
%% "Random" initial route + twoopt improvement
r = [1:n 1:n];
[r5,TD5] = twoopt(r,rTDh)
plotshmt(sh,XY,r5,tr,false)
pplot(XY,num2cell(1:n+1))
%% Random + twoopt
rng(1234)
r = randperm(n);
r = [r r];
[r5,TD5] = twoopt(r,rTDh); TD5
plotshmt(sh,XY,r5,tr,false)
pplot(XY,num2cell(1:n+1))

%% Example 3: 51-city TSP
%% Data
clear, close all
vrpnc1
D = dists(XY,XY,2);
n = size(XY,1)-1;

sh = vec2struct('b',2:n+1,'e',1);
sh = fliplr(sh);
tr = struct('b',1,'e',1);

rTDh = @(rte) rteTC(rte,sh,D,tr);
%% twoopt(savings): offline procedure (all shmt initially available)
IJS = pairwisesavings(rTDh,sh);
[r1,TD1] = twoopt(savings(rTDh,sh,IJS,true),rTDh,true);
plotshmt(sh,XY,r1,tr,false)
pplot(XY,num2cell(1:n+1))
%% Insertimprove: offline procedure (insert + improve each shmt added)
rng(43891)
idxsh = randperm(length(sh))
tic,[r2,TD2] = insertimprove(idxsh,rTDh,sh),toc
%% twoopt(Mincostinsert): online procedure (improve as each shmt added)
r3 = [idxsh(1) idxsh(1)];
tic,for i = idxsh(2:end)
   [r3,TD3] = twoopt(mincostinsert([i i],r3,rTDh,sh),rTDh);
end,toc,TD3
%% Mincostinsert + twoopt: online procedure (improve only at end)
r4 = [idxsh(1) idxsh(1)];
tic,for i = idxsh(2:end)
   r4 = mincostinsert([i i],r4,rTDh,sh);
end
[r4,TD4] = twoopt(r4,rTDh);toc,TD4
%% Randomize savings + twoopt
rng(832472)
help randreorder
%% (run)
IJS2 = randreorder(IJS,0.1);  % 10% chance of moving row to bottom of array
tic,[r5,TD5] = twoopt(savings(rTDh,sh,IJS2),rTDh),toc
