% Facility Location 2: Computational Geometry, Matlog, and Metric Distances

%% Computational Geometry
%% Create points
rng(11094)
XY = rand(20,2)*7.5 - 3.75;
dt = delaunayTriangulation(XY);
close all, figure()
plot(XY(:,1),XY(:,2),'k.','MarkerSize',10),shg
axis([-4 4 -4 4]),shg
axis square
%% Convex Hull
idx = convexHull(dt); hold on
plot(XY(idx,1),XY(idx,2),'ro-'),shg
title('Convex Hull')
%% Delaunay
hold on
triplot(dt,'-r');
plot(XY(:,1),XY(:,2),'k.','MarkerSize',10),shg
title('Delaunay Triangulation')
hold off
%% Voronoi
hold on
voronoi(XY(:,1),XY(:,2),'b-')
plot(XY(:,1),XY(:,2),'k.','MarkerSize',10),shg
plot(XY(idx,1),XY(idx,2),'ro'),shg
title('Voronoi Diagram')
hold off

%% Matlog: Logistics Engineering Toolbox
%% Add path to Matlog
% First, go to directory where Matlog has been unzipped to
pwd
path
path(path,pwd)
path
matlabroot
userpath
which startup
edit startup
%% Check to see if working
help matlog
doc matlog
doc dists

%% Metric Distances
%% 3-Point Example
xy1 = [1 1], P = [1 1; 7 1; 4 5]
d2h = @(x,P) sqrt(sum((x - P).^2, 2));            % Euclidean
d1h = @(x,P) sum(abs(xy1 - P), 2);                % Rectilinear
dInfh = @(x,P) max(abs(xy1 - P), [], 2);          % Chebychev
dph = @(x,P,p) (sum(abs((x - P)).^p, 2)).^(1/p);  % General lp
d2h(xy1,P)
dph(xy1,P,2)
[d1h(xy1,P) dph(xy1,P,1)]
[dInfh(xy1,P) dph(xy1,P,Inf)]
[dInfh(xy1,P) dph(xy1,P,100)]
[dInfh(xy1,P) dph(xy1,P,1000)]
%% Matlog's DISTS function
xy2 = [2 3]
d = dists(xy1,xy2,1)
d = dists(xy1,xy2,2)
d = dists(xy1,xy2)
d = dists(xy1',xy2')
d = dists(xy1,xy2,'mi')
% d = dists(xy1,xy2','mi')   % Error
d = dists(xy1,P)
d = d2h(xy1,P)
d = dists(P,P)
