% Facility Location 4: Multifacility Location and Aggregate Demand Points

%% Minisum Multifacility Location Problem
%% Single-facility location
P = [1 1;2 0;2 3], w = [4 3 5]
TCh = @(x) w*dists(x,P,2)';
[x,TC] = fminsearch(TCh,mean(P,1))
[x,TC] = minisumloc(P,w,2)
%% Multifacility location
W = [4 3 5;2 3 0], V = [0 1;0 0]
TCh = @(X) sum(sum(W.*dists(X,P,2))) + sum(sum(V.*dists(X,X,2)));
[X,TC] = fminsearch(TCh,randX(P,length(V)))
[X,TC] = minisumloc(P,W,2,V)
%% Two single-facility locations
V = []
[x1,TC1] = minisumloc(P,W(1,:),2)
[x2,TC2] = minisumloc(P,W(2,:),2)
TC1 + TC2
[X,TC] = minisumloc(P,W,2,V)
[X,TC] = minisumloc(P,W,2)    % rows of W determine number of NFs

%% Facility Location–Allocation Problem
%% EXAMPLE 1: I-40 Cities (1-D location problem)
P = [50 150 190 220 270 295 420]'
m = size(P,1)
w = 1:m
X = [100 300]'
n = size(X,1)
p = 1;
%% Calc TC for a given location X
D = dists(X,P,p);
a = argmin(D);
W = full(sparse(a,1:m,w,n,m))
TC = sum(sum(W.*D))
%% Make TC a function of X
TCh = @(X) full(sum(sum(sparse(argmin(dists(X,P,p)),1:m,w,n,m) .* ...
   dists(X,P,p))));
%% Get TC for a particular X
TCh(X)
%% Plot surface
[X1,X2] = meshgrid(linspace(0,500),linspace(0,500));
Z = zeros(size(X1));
for i = 1:size(X1,1)
    for j =1:size(X2,2)
        Z(i,j) = TCh([X1(i,j) X2(i,j)]');
    end
end
contour(X1,X2,Z,50),shg
axis square
xlabel('X1')
ylabel('X2')
%% First Approach: Integrated Formulation
TCh = @(X) full(sum(sum(sparse(argmin(dists(X,P,p)),1:m,w,n,m) .* ...
   dists(X,P,p))));
rng(2135)
X0 = randX(P,n)  %  use RANDX to generate n random staring points within 
                 %   P's bounding rectangle
[X,TC] = fminsearch(TCh,X0)
%% (run again)
[X1,TC1] = fminsearch(TCh,randX(P,n))
hold on
plot(X1(1),X1(2),'r.'),shg
%% Second Approach: Alternating Formulation
% Code for ALA procedure:
TCh = @(W,X) sum(sum(W.*dists(X,P,p)));
alloc_h = @(X) full(sparse(argmin(dists(X,P,p)),1:m,w,n,m));
loc_h = @(W,X0) fminsearch(@(X) TCh(W,X),X0);
rng(5638)
%% (run)
X2 = randX(P,n);          % initial locate
TC2 = Inf;
done = false;
while ~done
   W2i = alloc_h(X2);     % allocate
   X2i = loc_h(W2i,X2);   % locate
   TC2i = TCh(W2i,X2i);
   fprintf('%e\n',TC2i);
   if TC2i < TC2
      TC2 = TC2i; X2 = X2i; W2 = W2i;
   else
      done = true;
   end
end
X2, TC2
%% Use Matlog's ALA
rng(5638)
[X2,TC2] = ala(randX(P,n),w,P,p)

%% EXAMPLE 2: NC & SC Cities (2-D location problem)
[P,w] = uscity10k('XY','Pop',mor({'NC','SC'},uscity10k('ST')));
m = size(P,1)
n = 2
p = 'mi'
%% Plot EFs
makemap(P)
pplot(P,'r.')
%% Solve ALA for single initial set of locations
rng(37277)
pauseplot('set',2)
ala(randX(P,n),w,P,p)
pauseplot('set',0)
%% Single run of ALA
[X,TC] = ala(randX(P,n),w,P,p);
lonlat2city(X), fprintf('TC = %f\n\n',TC)
%% Take the best of 'nruns' runs of ALA
nruns = 10; TC2 = Inf;
for i = 1:nruns
   [X2i,TC2i,W2i] = ala(randX(P,n),w,P,p); 
   fprintf('%d %e\n',i,TC2i);
   if TC2i < TC2, TC2 = TC2i; X2 = X2i; W2 = W2i; end
end
TC, TC2
%% Compare with Integrated Formulation
% Search in (n x d)-dimensional space
TCh = @(X) full(sum(sum(sparse(argmin(dists(X,P,p)),1:m,w,n,m) .* ...
   dists(X,P,p))));
[X3,TC3] = fminsearch(TCh,randX(P,n))
lonlat2city(X3)
TC2, TC3
%% Compare Integrated and Alternating Formulations 
rng(37277)
tic, for i=1:10, [X3,TC3] = fminsearch(TCh,randX(P,n)); end, toc
rng(37277), close all
tic, for i=1:10, [X,TC] = ala(randX(P,n),w,P,p); end, toc
%% Compare for greater number of NFs
n = 20;
TCh = @(X) full(sum(sum(sparse(argmin(dists(X,P,p)),1:m,w,n,m) .* ...
   dists(X,P,p))));
rng(37277)
tic, for i=1:5, [X3,TC3] = fminsearch(TCh,randX(P,n)); end, toc
rng(37277), close all
tic, for i=1:5, [X2,TC2] = ala(randX(P,n),w,P,p); end, toc
TC3, TC2
%% Edge Case: Unallocated NFs
% Don't check for unallocated NFs (detected by all 0's in row of W)
n = 2;
rng(5638)
X0 = randX(P,n);
X0(1,:) = [0 0]   % Lon-lat 0,0 off the coast of Nigeria
TCh = @(W,X) sum(sum(W.*dists(X,P,p)));
alloc_h = @(X) full(sparse(argmin(dists(X,P,p)),1:m,w,n,m));
loc_h = @(W,X0) fminsearch(@(X) TCh(W,X),X0);
TC = Inf;
done = false; X = X0;
while ~done
   Wi = alloc_h(X);
   Xi = loc_h(Wi,X);
   TCi = TCh(Wi,Xi);
   if TCi < TC
      TC = TCi; X = Xi; W = Wi;
   else
      done = true;
   end
end
X, TC, spy(W)
%% Use ALA, where any unallocated NFs are randomly relocated to EFs
[X,TC,W] = ala(X0,w,P,p);
X, TC, spy(W)

%% EXAMPLE 3: Best Retail Warehouse Locations in U.S.
% Note: Using 2010 Census data vs. 2000 data in Table in slide/notes
[P,w] = uszip3('XY','Pop',...
   ~mor({'AK','HI','PR'},uszip3('ST')) & uszip3('Pop') > 0);
rng(38288)
Name = uscity('Name'); ST = uscity('ST');
%% n =  1
[X,TC] = ala(randX(P,1),w,P,'mi');
lonlat2city(X)
X1 = uscity('XY',strcmp('Bloomington',Name) & strcmp('IN',ST));
delta = dists(X,X1,'mi')
%% calc average transit time
dPerDay = 400  % Trucks traveling at 400 miles per day
g = 1.2       % Circuity factor
d =  dists(X,P,'mi') * g;
%% (re-calc cell)
mean(d)                   % Average distance
sum(d(:).*(w(:)/sum(w)))  % Demand weighted average distance
t = sum((d(:)/dPerDay) .* (w(:)/sum(w)))
%% n = 2
nruns = 5; TC = Inf;
for i = 1:nruns
   [Xi,TCi,Wi] = ala(randX(P,2),w,P,'mi');
   fprintf('%d %e\n',i,TCi);
   if TCi < TC, TC = TCi; X = Xi; W = Wi; end
end
lonlat2city(X)
X2 = uscity('XY',mand({'Ashland','Palmdale'},uscity('Name'),...
   {'KY','CA'},uscity('ST')));
delta = round(dists(X,X2,'mi'))
%% General n
n = 8
nruns = 5; TC = Inf;
rng(9348)
for i = 1:nruns
   [Xi,TCi,Wi] = ala(randX(P,n),w,P,'mi');
   fprintf('%d %e\n',i,TCi);
   if TCi < TC, TC = TCi; X = Xi; W = Wi; end
end
lonlat2city(X)
alaplot(X,W,P)

%% Demand Point Aggregation
%% (a) Centroid for sum weighted distance 
xcog1D = @(x,w) w(:)'*x(:)/sum(w);
P = [50 150 190 220 270 295 420]'
m = size(P,1)
w = 1:m
xcog = xcog1D(P,w)
xmed = minisumloc(P,w,1)
x0 = 0;
TC0 = w*P
TCcog = sum(w)*xcog
TCmed = sum(w)*xmed
%% (b) Not-centroid for sum weighted squared distance
xd2 = @(x,w) sqrt(w(:)'*x(:).^2/sum(w))
TC0 = w*P.^2
TCcog = sum(w)*xcog^2
TCxd2 = sum(w)*xd2(P,w)^2
mdisp(TCxd2)
%% (c) Create 2-digit ZIP code aggregate data
clear XY Area Pop
xycog = @(XY,w) [w(:)'*XY(:,1) w(:)'*XY(:,2)]/sum(w);
z = uszip3;
z.Code2 = floor(z.Code3/10);
Code2 = unique(z.Code2);
for i = 1:length(Code2)
   zi = uszip3(mor(Code2(i),z.Code2));
   XY(i,:) = xycog(zi.XY,zi.Pop);
   Area(i) = sum(zi.LandArea);
   Pop(i) = sum(zi.Pop);
end
save uszip2 XY Area Pop
makemap(XY)
pplot(XY,'r.')
