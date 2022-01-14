%% Network Models 2: Shortest Path Problem and Road Networks

%% Plot random graph using GRAPH object
help graph
help digraph
rng(12912)
W = triu(rand(20),1); spy(W)
W = W + W'; spy(W),shg
W(W<.8) = 0;
W(W>0) = 1; spy(W),shg
G = graph(W)
plot(G)
t = G.Edges                  % table
IJC = [t.EndNodes t.Weight]  % table to matrix
IJC = adj2list(W)            % matrix

%% 1. Shortest Path Problem Example
%% Create data 
IJD = [
     1    -2     4
     1    -3     2
     2    -4     5
     2    -3     1
     3    -4     8
     3    -5    10
     4    -5     2
     4    -6     6
     5    -6     3];
%% Solve as MCNF
s = [1 0 0 0 0 -1];
lp = mcnf2lp(IJD,s);
[x,TC,XFlg,out] = lplog(lp{:})
[f,TC,nf] = lp2mcnf(x,IJD,s)
%% Dijkstra's algorithm
help dijkdemo
[d,p] = dijkdemo(list2adj(IJD),1,6)
%% Computational complexity
n = 6      % nodes in example
vdisp('n^4,n^2,n*log(n)')
n = 70000  % approx road nodes in U.S.
vdisp('n^4,n^2,n*log(n)')

%% 2. Delaunay Network from Cities Centered around Raleigh
%% Make network using cities of 30k pop. within 100 miles of Raleigh
Ral = uscity('XY',mand({'Raleigh'},uscity('Name'),{'NC'},uscity('ST')));
[Name,XY]=uscity10k('Name','XY', ...
   (dists(Ral,uscity10k('XY'),'mi') < 100)' & uscity10k('Pop') > 30000);
makemap(XY)
pplot(XY,'r.')
%% Use Delaunay triangulation as road network
tri = delaunay(XY(:,1),XY(:,2));  % Delaunay triangulation
IJ = tri2list(tri);  % Convert to arc list
d = diag(dists(XY(IJ(:,1),:),XY(abs(IJ(:,2)),:),'mi'));
d = d * 1.2;  % Convert great circle to estimated road distances
d = round(d);
IJD = [IJ d];
pplot(IJD,XY,'m-')
pplot(IJD,num2cellstr(d),XY)
%% Number nodes
% Two ways to number nodes: 
% (1) Numbers in parentheses next to node point:
% pplot(XY,'r.'), nodelab = strcat(strcat('(',num2cellstr(1:size(XY,1))),')'); pplot(XY,nodelab)
% (2) Number inside of node:
pplot(XY,'NumNode','MarkerEdgeColor','k')
pplot(XY,Name)
%% Find shortest path from High Point (node 10) to Goldsboro (node 7)
[d,p] = dijkdemo(list2adj(IJD),10,7)
Name(p)
pplot({p},XY,'y-','LineWidth',3,'DisplayName','dijk')
%% Minimum Spanning Tree (Kruskal algorithm)
t = minspan(IJD);
pplot(IJD(t~=0,:),XY,'g-','LineWidth',2,'DisplayName','minspan')

%% 3. Plot U.S. Interstate Road Network
%% Original
[XY,IJD] = subgraph(usrdnode('XY'),[],...
                    usrdlink('IJD'),usrdlink('Type')=='I');
makemap(XY)
pplot(IJD,XY,'r-')
title('U.S. Interstate Road Network')
%% Distance from node 1 to all other nodes (Interstate insections)
tic, d = dijk(list2adj(IJD),1); toc
size(IJD,1)
%% Thinned
tIJD = thin(IJD);
[XY,IJD] = subgraph(XY,[],tIJD);
pplot(IJD,XY,'k-')

%% 4. Shortest Road Travel Time
%% Find cities with 30k pop. within 100 miles of Raleigh
Ral = uscity('XY',mand({'Raleigh'},uscity('Name'),{'NC'},uscity('ST')));
[Name,XY1]=uscity10k('Name','XY',(dists(Ral,uscity10k('XY'),'mi')<100)' ...
   & uscity10k('Pop')>30000);
%% Get road network
expansionAroundXY = 0.1;
[XY2,IJD,isXY,isIJD] = subgraph(usrdnode('XY'),...
   isinrect(usrdnode('XY'),boundrect(XY1,expansionAroundXY)),...
   usrdlink('IJD'));
%% Label type of road
s = usrdlink(isIJD);
isI = s.Type == 'I';         % Interstate highways
isIR = isI & s.Urban == ' '; % Rural Interstate highways
isIU = isI & ~isIR;          % Urban Interstate highways
isR = s.Urban == ' ' & ~isI; % Rural non-Interstate roads
isU = ~isI & ~isR;           % Urban non-Interstate roads
%% Plot roads
makemap(XY2,0.03)  % 3% expansion
h = [];  % Keep handle to each plot for legend
h = [h pplot(IJD(isR,:),XY2,'r-','DisplayName','Rural Roads')];
h = [h pplot(IJD(isU,:),XY2,'k-','DisplayName','Urban Roads')];
h = [h pplot(IJD(isI,:),XY2,'c-','DisplayName','Interstate Roads')];
%% Add connector roads from cities to road network
[IJD11,IJD12,IJD22] = addconnector(XY1,XY2,IJD);
h = [h pplot(IJD12,[XY1; XY2],'b-','DisplayName','Connector Roads')];
h = [h pplot(XY1,'g.','DisplayName','Cities')];
%% Convert road distances to travel times (needs to be after ADDCONNECTOR)
v.IR = 75;  % Rural Interstate highways average speed (mph)
v.IU = 65;  % Urban Interstate highways average speed (mph)
v.R = 50;   % Rural non-Interstate roads average speed (mph)
v.U = 25;   % Urban non-Interstate roads average speed (mph)
v.C = 20;   % Facility to road connector average speed (mph)

IJT = IJD;
IJT(isIR,3) = IJD(isIR,3)/v.IR;
IJT(isIU,3) = IJD(isIU,3)/v.IU;
IJT(isR,3) = IJD(isR,3)/v.R;
IJT(isU,3) = IJD(isU,3)/v.U;

IJT22 = IJD22;                % road to road
IJT22(:,3) = IJT(:,3);
IJT12 = IJD12;                % facility to road
IJT12(:,3) = IJD12(:,3)/v.C;  % (IJD11 facility to facility arcs ignored)
%% Shortest time routes
n = size(XY1,1);
tic
[T,P] = dijk(list2adj([IJT12; IJT22]),1:n,1:n);
toc
%% Distance of shortest time route
W = list2adj([IJD12; IJD22]);
D = zeros(n);  
for i = 1:n
   for j = 1:n
      D(i,j) = locTC(pred2path(P,i,j),W);
   end
end
%% Find shortest path from High Point (node 10) to Goldsboro (node 7)
idx1 = 10; idx2 = 7;
[t,p] = dijk(list2adj([IJT12; IJT22]),idx1,idx2);
h = [h ...
   pplot({p},[XY1;XY2],'y-','LineWidth',2,'DisplayName','Shortest Path')];
pplot(XY1([idx1 idx2],:),Name([idx1 idx2]))
title(sprintf(...
   'From %s to %s: Distance %.2f mi, Time = %d hr %d min',...
   Name{idx1},Name{idx2},D(idx1,idx2),floor(t),round(60*(t-floor(t)))));
legend(h),shg
