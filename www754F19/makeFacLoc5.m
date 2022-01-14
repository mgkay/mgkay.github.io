% Facility Location 5: UFL Heuristics

%% Aggregate Demand Point Data Sources in Matlog
%% Data/function
x = uscity(mor({'NC'},uscity('ST')))  % only for labeling, not as demand pt
x = uszip3(mor({'NC'},uszip3('ST')))  % 3-digit ZIP codes (derived from 5)
x = uscounty(mor({'NC'},uscounty('ST')))  % Counties
x = uszip5(mor({'NC'},uszip5('ST')))  % 5-digit ZIP codes
x = uscenblkgrp(mor({'NC'},uscenblkgrp('ST')))  % Census block group
%% NC census block group data
[xy,TC] = minisumloc(x.XY,x.Pop','mi')
makemap(x.XY)
pplot(x.XY,'r.')
pplot(xy,'go','MarkerFaceColor','g')
title(sprintf('N = %d, Pop = %d, TC = %e',length(x.Pop),sum(x.Pop),TC))
lonlat2city(xy,uscity10k)
%% Top 20 cities in terms of population
[Pop,Name] = uscity50k('Pop','Name');
idx = argsort(-Pop);
Name(idx(1:20))
mand('Atlanta',Name)
%% ZIP codes
x = uszip5  % U.S.
makemap(x.XY), pplot(x.XY,'r.'), title('U.S.')
x = uszip3(~mor({'AK','HI','PR'},uszip3('ST')))
makemap(x.XY), pplot(x.XY,'r.'), title('Continental U.S.')
%% Census block group for Raleigh Combined Statistical Area (CSA)
[SCfips,Name,str] = uscounty('SCfips','Name','CSAtitle',...
   mor({'raleigh'},uscounty('CSAtitle')));
str = [str{1} ' CSA'];
mdisp(SCfips',Name,{'SCfips'},str)
x = uscenblkgrp(mor(SCfips,uscenblkgrp('SCfips')))
makemap(x.XY), pplot(x.XY,'r.'), title(str)

%% UFL Heuristics
%% EXAMPLE 1: UFL ADD Construction Procedure
%% Data: Asheville, Statesville, Greensboro, Raleigh, and Wilmington
P = [50 150 220 295 420]';
r = 1, f = 1, w = r * f
C = w * dists(P,P,1); mdisp(C)
k = [150 200 150 150 200] % k is different for each NF
%% Find first NF to add: 3
N = 1:size(C,1)
y = [];
setdiff(N,y)
for i = setdiff(N,y)
   i,TC = sum(k([y i])) + sum(min(C([y i],:),[],1))
end
y = 3
%% Find next NF to add: 1
setdiff(N,y)
for i = setdiff(N,y)
   i,TC = sum(k([y i])) + sum(min(C([y i],:),[],1))
end
y = [y 1]
%% Find next NF to add: none reduce TC, so STOP
setdiff(N,y)
for i = setdiff(N,y)
   i,TC = sum(k([y i])) + sum(min(C([y i],:),[],1))
end
%% Write as a general procedure, given k and C as inputs
y = [];
TC = Inf; done = false;
while ~done
   TC1 = Inf;                      % Stops if y = all NF,
   for i1 = setdiff(1:size(C,1),y) % since i1 = []
      TC2 = sum(k([y i1])) + sum(min(C([y i1],:),[],1));
      if TC2 < TC1
         TC1 = TC2; i = i1;
      end
   end
   if TC1 < TC % not true if y = all NF, since TC1 = Inf
      TC = TC1; y = [y i];
   else
      done = true;
   end
end
y,TC
%% Solve using UFLADD in Matlog
[y,TC,X] = ufladd(k,C);
y,TC,mdisp(X)

%% EXAMPLE 2: UFL DROP Construction Procedure
%% Same data as Example 1
%% Find first NF to drop: 2
y = 1:size(C,1)
TC = sum(k(y)) + sum(min(C))
for i = y
   i,TC = sum(k(setdiff(y,i))) + sum(min(C(setdiff(y,i),:),[],1))
end
y(2) = []
%% Find next NF to drop: 4 or 5, pick 4
for i = y
   i,TC = sum(k(setdiff(y,i))) + sum(min(C(setdiff(y,i),:),[],1))
end
y(y == 4) = []
%% Find next NF to add: none reduce TC, so STOP
for i = y
   i,TC = sum(k(setdiff(y,i))) + sum(min(C(setdiff(y,i),:),[],1))
end
%% Solve using UFLDROP in Matlog
[y,TC,X] = ufldrop(k,C);
y,TC,mdisp(X)

%% EXAMPLE 3: UFL EXCHANGE Improvement Procedure
%% Use data and results from Example 1
y = ufladd(k,C)
%% Exchange procedure, given k, C, and y as inputs
TC = sum(k(y)) + sum(min(C(y,:),[],1));
TC1 = Inf;
done = false;
while length(y) > 1 && ~done
   for i1 = y
      for j1 = setdiff(1:size(C,1),y)
         y1 = [setdiff(y,i1) j1];
         TC2 = sum(k(y1)) + sum(min(C(y1,:),[],1));
         if TC2 < TC1
            TC1 = TC2; i = i1; j = j1;
         end
      end
   end
   if TC1 < TC
      TC = TC1;
      y = [setdiff(y,i) j];
   else
      done = true;
   end
end
y, TC

%% EXAMPLE 4: UFL Hybrid Algorithm
[y1,TC1] = ufladd(k,C);
done = false;
while ~done
   [y,TC] = uflxchg(k,C,y1);
   if ~isequal(y,y1)
      [y1,TC1] = ufladd(k,C,y);
      [y2,TC2] = ufldrop(k,C,y);
      if TC2 < TC1
         TC1 = TC2; y1 = y2;
      end
      if TC1 >= TC
         done = true;
      end
   else
      done = true;
   end
end
y, TC

%% EXAMPLE 5: P-median location
% Can use modified UFLADD with no fixed costs and keep adding until p NFs
k0 = 0;
y = [];
p = 3
y = ufladd(k0,C,y,p);
[y,TC,X] = uflxchg(k0,C,y);
y,TC,mdisp(X)
TC + sum(k(y))  % Make TC compariable to UFL
%% P-median procedure, given p and C as inputs
y = ufladd(0,C,[],p);
[y,TC] = uflxchg(0,C,y);
y1 = ufldrop(0,C,[],p);
[y1,TC1] = uflxchg(0,C,y1);
if TC1 < TC
   TC = TC1; y = y1;
end
y, TC

%% Bottom-Up vs Top-Down Analysis
%% Bottom-Up: HW 3 Question 3
city2lonlat = @(city,st) ...
   uscity('XY',mand(city,uscity('Name'),st,uscity('ST')));
P = city2lonlat({'Detroit','Gainesville','Memphis'},{'MI','FL','TN'});
f = [48 24 32];
r = 2;
D = dists(P,P,'mi');
g = mean([1057/D(1,2) 754/D(1,3) 719/D(2,3)])  % Using fastest rte per Gmap
[xy_opt,TCopt] = minisumloc(P,f*r*g,'mi');
xyCary = city2lonlat('Cary','NC');
TCcary = sum(f.*dists(xyCary,P,'mi')) * g * r;
vdisp('TCopt,TCcary,TCcary - TCopt')
%% Top-Down: estimate r
f = [480 240 320];  % (ton/yr)
r_nom = TCcary/(sum(f.*dists(xyCary,P,'mi')))  % Don't need circuity factor
[xy_opt,TCopt] = minisumloc(P,f*r_nom,'mi');   % since nominal cancels
vdisp('TCopt,TCcary,TCcary - TCopt')
