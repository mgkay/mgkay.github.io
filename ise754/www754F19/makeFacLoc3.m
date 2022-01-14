% Facility Location 3: Geocoding and Allocation

%% NC City data
doc matlog
doc nccity
s = nccity  % structure returned
s.Name      % cell array returned
%% Cell arrays
c = {[1 2],[3 4]}
c{:}
m = [1 2; 3 4]
c = {[1 2],[3 4 5]}
c{:}
% m = [1 2; 3 4 5]   % Error
s
c = {[1 2],[3 4 5],s}
c(3)   % 1x1 cell array returned
c{3}   % structure returned
%% City name
[XY,Name] = nccity('XY','Name');  % Separate arrays for XY and Name
s = nccity;                       % Structure with XY and Name fields
strcmp('Raleigh',s.Name)
is = strcmp('Raleigh',s.Name);
nnz(is)
idx = find(is)
s.Name{idx}
s.XY(idx,:)
XY = nccity('XY')
xyRal = nccity('XY',idx)
nccity(idx)
%% NC City name to lon-lat
% Using multiple commands
idx = find(strcmp('Raleigh',s.Name))
xyRal = s.XY(idx,:)
idx = find(strcmp('raleigh',s.Name))  % Empty array returned if no match
s.XY(idx,:)
% Using function handle
city2lonlat = @(city,s) s.XY(strcmp(city,s.Name),:)
city2lonlat('Raleigh',s)
s2 = uscity                 % U.S. cities
city2lonlat('Raleigh',s2)   % All Raleigh's in U.S.
city2lonlat('Raleigh',uscity)
city2lonlat = @(city) nccity('XY',strcmp(city,nccity('Name')))
xyRal = city2lonlat('Raleigh')
xyRal = city2lonlat('raleigh')
city2lonlat = @(city) nccity('XY',strcmpi(city,nccity('Name')))
xyRal = city2lonlat('raleigh')
%% Add second city
xyBoo = city2lonlat('boone')
%% Great circle distances
dists(xyRal,xyBoo,'mi')
dists(xyRal,s.XY,'mi')
%% Find furthest city from Raleigh
d = dists(xyRal,s.XY,'mi');
max(d)
[v,idx] = max(d)
s.Name{idx}
[~,idx] = max(d)
idx = argmax(d)
%% Plot all NC cities
makemap
makemap(s.XY)
pplot(s.XY,'r.')
pplot(s.XY,s.Name)
%% Mercator projection
xyRal
proj(xyRal)
invproj(proj(xyRal))

%% Find population-weighted optimal NC location
TCh = @(xy) dists(xy,s.XY,'mi') * s.Pop
xy = fminsearch(TCh,mean(s.XY))
pplot(xy,'g*')
s.Name{argmin(dists(xy,s.XY,'mi'))}  % Closest nccity city
lonlat2city(xy)
doc lonlat2city
lonlat2city(xy,uscity)
lonlat2city(xy,uscity10k)
%% NC zoo
xyZoo = [35.621096 -79.755075]
pplot(fliplr(xyZoo),'kv')        % Flip lat-lon to lon-lat
%% Matlog's MINISUMLOC
makemap
% [X,TC,XFlg,X0] = minisumloc(P,W,p,V,X0,opt)
opt = minisumloc('defaults')
opt.IterPlot = gca;
xy0 = [0 0];
P = s.XY;
w = s.Pop(:)';       % Has to be a row vector (n x m, where n = 1)
opt.SearchTech = 1;  % 1 => only FMINUNC (gradient-based search)
xy = minisumloc(P,w,'mi',[],xy0,opt)
delete(findobj('Tag','iterplot'))   % Delete points plotted
opt.SearchTech = 2;  % 2 => only FMINSEARCH (Nelder-Mead direct search)
xy = minisumloc(P,w,'mi',[],xy0,opt)

%% NC cities with populations of at least 50k
XY50 = s.XY(s.Pop>=50000,:)
makemap(XY50)
pplot(XY50,'r.')
pplot(XY50,s.Name(s.Pop>=50000))
%% Create data for NC cities with at least 125K population
s = nccity
is = s.Pop > 125000;
idx = find(s.Pop > 125000)
s = nccity(idx)
s = nccity(nccity('Pop') > 125000)
%% Can use structure or can directly assign to variables
[Name,XY,w] = nccity('Name','XY','Pop',nccity('Pop') > 125000)
%% Find indices for Raleigh and Charlotte
s.Name
% idxDC = strcmp({'Raleigh','Charlotte'},s.Name)   % Error
isDC = strcmp('Raleigh',s.Name) | strcmp('Charlotte',s.Name)
idxDC = find(strcmp('Raleigh',s.Name) | strcmp('Charlotte',s.Name)) % Wrong
idxDC = find(strcmp('Charlotte',s.Name) | strcmp('Raleigh',s.Name))
idxDC = [find(strcmp('Raleigh',s.Name)); find(strcmp('Charlotte',s.Name))]
%% Use MAND so that index order is correct
idxDC = mand({'Raleigh','Charlotte'},s.Name)
idxDC = mand({'Charlotte','Raleigh'},s.Name)
help mand
idxDC = mand({'Raleigh','Char'},s.Name)
% idxDC = mand({'Raleigh','C'},s.Name)   % Error
idxDC = mand({'Raleigh','Ch'},s.Name)
idxDC = mand({'ral','Ch'},s.Name)
%% Allocate city population to Raleigh and Charlotte based on closeness 
D = dists(s.XY(idxDC,:),s.XY,'mi')
[n,m] = size(D)
argmin(D)
s.Name
w = s.Pop'
a = argmin(D)
W = zeros(n,m)
W = sparse([],[],[],n,m)
W = sparse(n,m)                % abbreviates sparse([],[],[],n,m) 
W = sparse(a,1:m,w,n,m)        % see Basic Concepts sec. 17 and 18
W = full(sparse(a,1:m,w,n,m))
TD = sum(sum(W.*D))
%% Determine total population allocated to Raleigh and Charlotte
mdisp(W)
sum(W,1)
sum(W,2)
%% Convert GC distances to estimated actual road distance using circuity
s.Name
D
D(1,2)
g = 167/D(1,2)          % Raleigh to Charlotte
D(2,1)
g(end+1) = 160/D(2,1)   % Charlotte to Cary
D(1,5)
g(end+1) = 76.7/D(1,5)  % Raleigh to Fayetteville
g = mean(g)
Dest = g*D
Dest(1,7)               % Raleigh to Winston-Salem estimated road
D(1,7)                  % Raleigh to Winston-Salem great circle
dact17 = 103            % Raleigh to Winston-Salem actual road
Dest(1,7)/dact17

%% Create NCCITY data from USCITY data
s = uscity
help uscity
s = uscity(strcmp('NC',s.ST))
makemap(s.XY)
pplot(s.XY,'r.')
s = uscity(strcmp('NC',uscity('ST')) & uscity('Pop') >= 10000)

%% Use USCITY data to find indices for Raleigh and Charlotte
% idxDC = mand({'Raleigh','Charlotte'},uscity('Name')) % Error: multiple 
                                                       % Raleigh's in U.S.
idxDC = mand({'Raleigh','Charlotte'},uscity('Name'),...
   {'NC','NC'},uscity('ST'))
uscity(idxDC(1))

%% Get all cities in NC and VA
s = uscity(strcmp('NC',uscity('ST')) | strcmp('VA',uscity('ST')))
makemap(s.XY)
pplot(s.XY,'r.')
s = uscity(mor({'NC','VA'},uscity('ST')))   % Using MOR (Multiple OR)
help mor

%% Cities with population greater than 10K in continental U.S.
s = uscity(uscity('Pop') > 10000)
makemap(s.XY)
pplot(s.XY,'r.')
s = uscity(~mor({'AK','HI','PR'},uscity('ST')) & uscity('Pop') > 10000)
makemap(s.XY)
pplot(s.XY,'r.')

