%% Routing 1: Traveling Salesman Problem

%% TSP Construction: Spacefilling curve
doc matlog
help vrpnc1
vrpnc1
h = pplot(XY,'r.');
help tspspfillcur
pplot(XY,num2cell(1:size(XY,1)))
loc = tspspfillcur(XY)
pplot({loc},XY,'g','Tag','locplot')
C = dists(XY,XY,2);
help loccost
c = loccost(loc,C)
C(1,7)
type loccost
sum(c)
help tspspfillcur
TD = locTC(loc,dists(XY,XY,2))

%% TSP Improvement: 2-opt edge exchange
help tsp2opt
[loc,TC] = tsp2opt(loc,C,[],[],[],h); TC
% Given n nodes, number of sequences to verify local optimum at end:
n = 6
i = 1; for j = 3:n-1, disp([i j]), end              % first arc a
for i = 2:n-2,for j = i+2:n, disp([i j]), end, end  % arcs b to n - 1
syms i j n   % define as symbolic variables
pretty(simplify(symsum(1,j,3,n-1)+symsum(symsum(1,j,i+2,n),i,2,n-2)))

%% TSP Construction: Convex hull insertion algorithm
help tspchinsert
h = pplot(XY,'r.');
pplot(XY,num2cell(1:size(XY,1)))
loc = tspchinsert(XY,h);
TDch = locTC(loc,dists(XY,XY,2))
[loc,TC] = tsp2opt(loc,C,[],[],[],h); TC

%% TSP Construction: Nearest neighbor algorithm
help tspnneighbor
h = pplot(XY,'r.');
pplot(XY,num2cell(1:size(XY,1)))
[loc,TC] = tspnneighbor(C,1,h); TC
[loc,TC,bestvtx] = tspnneighbor(C,[],h); TC
[loc,TC] = tsp2opt(loc,C,[],[],[],h); TC

%% TSP Construction: Random with improvement
help tsp2opt
h = pplot(XY,'r.');
rng(100)
loc = [1 randperm(size(XY,1)-1)+1 1]
TD0 = locTC(loc,C)
[loc,TC] = tsp2opt(loc,C,[],[],[],h); TC
loc = [1 randperm(size(XY,1)-1)+1 1];
[loc,TC] = tsp2opt(loc,C,[],[],[],h); TC

