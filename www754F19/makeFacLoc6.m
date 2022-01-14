% Facility Location 6: Logistics Network Analysis

%% Area Adjustment for Aggregate Data Distances
%% 3-digit Zip
x = uszip3(mor({'NC'},uszip3('ST')) & uszip3('Pop') > 0)
%% Costs
P = x.XY;
D = dists(P,P,'mi')*1.2;    % mi  (distances without area adjustment)
f = x.Pop';
F = repmat(f,length(f),1);  % person
r = 1/10000;                % $/person-mi
C = r*D.*F;                 % $
k = repmat(6000,1,size(C,1));
%% Solve UFL
[y,TC] = ufl(k,C); y,TC
%% Plot
makemap(P), pplot(P,'r.')
pplot(P(y,:),'ko')
%% Area adjustment
a = x.LandArea;
dafh = @(XY1,a1,XY2,a2) max(1.2*dists(XY1,XY2,'mi'),...
   0.675*max(sqrt(a1(:)),sqrt(a2(:)')));
Da = dafh(P,a,P,a);  % Area-adjusted distances
Ca = r*Da.*F;
%% Solve UFL
[ya,TCa] = ufl(k,Ca); ya,TCa
pplot(P(ya,:),'cv')
fprintf('Pct increase total cost using area adjustment = %.2f%%\n',...
   100*((TCa - TC)/TC))

%% Popco Bottling Company Example
%% (Alt 1) Input spreadsheet data to numeric array
X = xlsread('PopcoData.xlsx','plant');
DC = X(:,[2 1]);
fDC = X(:,3);
TPC = X(:,4);
TDC = X(:,5);
%% (Alt 2) Input spreadsheet as table data
T = readtable('PopcoData.xlsx')
S = table2struct(T)
DC = [[S.lon]' [S.lat]'];
fDC = [S.demand]';
TPC = [S.prod_cost]';
TDC = [S.dist_cost]';
%% Plot plants/DCs
makemap(DC)
pplot(DC,'r.')
%% Plot 
figure
plot(fDC,TPC,'r.'),shg
%% Est fixed cost (Step 1)
x = fDC;
y = TPC;
yest = @(x,p) p(1) + p(2)*x;
fh = @(p) sum((y - yest(x,p)).^2);
ab = fminsearch(fh,[0 1])
k = ab(1), cp = ab(2)
hold on, fplot(@(x) yest(x,ab),[0 max(x)],'k-'), shg, hold off
%% Get aggregate demand points (Step 2)
[P,q,a] = uszip3('XY','Pop','LandArea',...
   ~mor({'AK','HI','PR'},uszip3('ST')) & uszip3('Pop') > 0);
%% Area-adjusted distance handle
dafh = @(XY1,a1,XY2,a2) max(1.2*dists(XY1,XY2,'mi'),...
   0.675*max(sqrt(a1(:)),sqrt(a2(:)')));
%% Allocate demand to DCs
idx = zeros(1,length(q));
for i = 1:length(q)
   [di,idxi] = min(dafh(P(i,:),a(i),DC,0));   % Actual DCs have 0 area
   dmax = 200;   % Max plant-to-customer distance for round-trip travel
   if di <= dmax
      idx(i) = idxi;
   end
end
%% Remove unallocated points
P(idx==0,:) = [];
q(idx==0) = [];
a(idx==0) = [];
idx(idx==0) = [];
%% Test for DCs without demand
idx0 = setdiff(1:length(fDC),unique(idx))
%% Allocate DC demand to customers based on population (Step 3)
D = dafh(DC,0,P,a);
f = zeros(length(q),1);
for i = 1:length(fDC)
   Mi{i} = find(argmin(D) == i);
   f(Mi{i}) = fDC(i)*(q(Mi{i})/sum(q(Mi{i})));
end
vdisp('sum(fDC),sum(f)')
%% Nominal transport rate (Step 4)
F = sparse(argmin(D),1:length(f),f);
r = sum(TDC)/sum(sum(F.*D))  % nominal network-wide $/ton-mi 
%% Cost matrix for UFL (Step 5)
D = dafh([P; DC],0,P,a);   % Include demand + DC locations for NF sites
C = r*(f(:)'.*D);
%% UFL (Step 6)
[y,TC,X] = ufl(k,C);
nNF = length(y)
TDC_new = full(sum(sum(C.*X)))
TC_new = length(y)*k + TDC_new
TDC_orig = sum(TDC)
TC_orig = k * size(DC,1) + TDC_orig
100*TDC_new/TDC_orig
100*TC_new/TC_orig
%% Plot new DCs
NFsites = [P; DC];
pplot(NFsites(y,:),'go')
%% Save data for later to create MILP model
save popcoUFL k C S
