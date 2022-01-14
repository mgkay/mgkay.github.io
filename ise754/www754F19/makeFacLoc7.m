% Facility Location 7: Discrete Location and MILP

%% EXAMPLE 1: Branch & Bound
%% LP
% [X,TC] = linprog(c,A,b,Aeq,beq,LB,UB)
c = [6 8];
A = [2 3; 2 0];
b = [11 7]';
[x,TC] = linprog(-c,A,b)
lp = {-c,A,b,[],[],[],[]};
lp{:}
[x,TC] = linprog(lp{:})

%% MILP
%% (Alt 1a): Use  Matlab's INTLINPROG directly
% [X,TC] = intlinprog(c,intcon,A,b,Aeq,beq,LB,UB)
doc intlinprog
intcon = [1 2];  % integer varible indices
ilp = {lp{1},intcon,lp{2:end}}
[x,TC] = intlinprog(ilp{:})

%% (Alt 1b) Use Milp object for INTLINPROG
doc Milp
clear mp
mp = Milp
mp.Model
mp.addobj('max',c)
mp.Model
mp.addcstr(A,'<=',b)
mp.Model
mp.addctype('I')
mp.Model
mp.dispmodel
ilp = mp.milp2ilp
[x,TC] = intlinprog(ilp{:})
x = mp.namesolution(x)
TC

%% (Alt 2a) Use Gurobi directly
doc gurobi
clear model params
model.modelsense = 'maximize';
model.obj = c;
model.lb = [0 0];
model.ub = [Inf Inf];
model.vtype = 'II';
model.A = sparse(A);       % Must be sparse
model.sense = ['<';'<'];
model.rhs = b;
model                      % "model" is regular Matlab structure
params.outputflag = 1;
result = gurobi(model,params);
result
x = result.x
TC = result.objval

%% (Alt 2b) Use Milp object for Gurobi
clear params
model = mp.milp2gb
params.outputflag = 1;
result = gurobi(model, params);
x = mp.namesolution(result.x)
TC = result.objval

%% EXAMPLE 2: UFL
clear all
k = [8     8    10     8     9     8]';
C = [0     3     7    10     6     4
     3     0     4     7     6     7
     7     4     0     3     6     8
    10     7     3     0     7     8
     6     6     6     7     0     2
     4     7     8     8     2     0];
[y,TC] = ufl(k,C)

%% %% Re-usable UFL Code
%% Create MILP model of UFL
clear mp
mp = Milp('UFL')
mp.Model
[n m] = size(C)
kn = iff(isscalar(k),repmat(k,1,n),k(:)');  % expand if k is constant value
mp.addobj('min',kn,C)  % min sum_i(ki*yi) + sum_i(sum_j(cij*xij))
n + n*m
for j = 1:m
   mp.addcstr(0,{':',j},'=',1)   % sum_i(xij) = 1
end
for i = 1:n
   mp.addcstr({m,{i}},'>=',{i,':'})  % m*yi >= sum_j(xij)  (weak form.)
end
mp.addub(1,1)
mp.addctype('B','C')         % only k are integer (binary)
mp.Model
%% Display Small MILP model
mp.dispmodel
%% Display Just the Constraints of Large MILP model
spy(mp.Model.A)
%% (Alt 1) Solve using Matlab's INTLINPROG
% x = intlinprog(c,intcon,A,b,Aeq,beq,LB,UB)
ilp = mp.milp2ilp;
[x,TC,exitflag,output] = intlinprog(ilp{:});
%% (Alt 2) Solve using Gurobi
clear model params
model = mp.milp2gb;
params.outputflag = 1;
result = gurobi(model,params);
x = result.x;
TC = result.objval;
%% Display solution
x = mp.namesolution(x)
TC
TCcalc = sum(kn.*x.kn) + full(sum(sum(C.*x.C)))
idxNF = find(round(x.kn))  % Round in case y > 0 & y < eps
nNF = sum(x.kn)
%% %% End re-usable code

%% EXAMPLE 3: Create MILP model of P-Median using Example 2 (force 3 NFs)
[y,TC] = pmedian(3,C)  % heuristic solution
%% Create MILP of UFL using re-usable code
k = 0;                 % no fixed cost
%% Convert to p-Median
mp.Model.name = 'pMedian'
mp.addcstr(1,0,'=',3)        % sum_i(yi) = 3, add constraint to force p NFs
mp.dispmodel
mp.Model
%%% Solve using re-usable code

%% EXAMPLE 4: UFL with n,m = 104
clear all
x = uszip5(mor({'NC'},uszip5('ST')) & uszip5('Pop') > 30000)
P = x.XY;
a = x.LandArea;
dafh = @(XY1,a1,XY2,a2) max(1.2*dists(XY1,XY2,'mi'),...
   0.675*max(sqrt(a1(:)),sqrt(a2(:)')));
Da = dafh(P,a,P,a);  % Area-adjusted distances
f = x.Pop';                 % person
r = 1/10000;                % $/person-mi
C = r*Da.*f;                % $
k = 500;  % repmat(500,1,size(C,1));
[y,TCufl] = ufl(k,C), nNFufl = length(y)
%% Plot solution
makemap(P), pplot(P,'r.')
pplot(P(y,:),'ko')
title([num2str(nNFufl) ' DCs using UFL' ])
%% Compare heuristic UFL to MILP UFL
%%% Solve using re-usable code to get TCcalc from solver
vdisp('nNFufl,nNF')
100*TCufl/TCcalc

%% EXAMPLE 5: Popco Bottling
clear all
load popcoUFL            % load saved data from previous heuristic solution
[y,TCufl] = ufl(k,C), nNFufl = length(y)
%%% Solve using re-usable code
vdisp('nNFufl,nNF')
100*TCufl/TCcalc

%% EXAMPLE 6: Set Covering and Packing Problems
clear all
close all
A = [1 1 0 0 0;
     1 0 0 1 0;
     0 0 1 1 0;
     0 1 0 0 0;
     0 1 1 0 0;
     0 0 0 1 1];
c = ones(1,size(A,2));
%% Set covering
mp = Milp('Set Covering')
mp.addobj('min',c)
mp.addcstr(A,'>=',1)   % sum_i(xi) >= 1, for all j in M
mp.addctype('B')
mp.dispmodel
%% Solve using INTLINPROG
ilp = mp.milp2ilp
x = intlinprog(ilp{:});
I = find(x)
%% Set packing
clear mp
mp = Milp('Set Packing')
mp.addobj('max',c)
mp.addcstr(A,'<=',1)   % sum_i(xi) <= 1, for all j in M
mp.addctype('B')
mp.dispmodel
%% Solve using INTLINPROG
ilp = mp.milp2ilp
J = find(intlinprog(ilp{:}))

%% EXAMPLE 7: Set Cover Location Problem
%% Find min number of NC cities from which other cities are within 50 mi
clear all
close all
s = nccity;
D = dists(s.XY,s.XY,'mi') * 1.2;
A = false(size(D));
A(D < 50) = true;
c = ones(1,size(A,2));
mp = Milp('Set Covering')
mp.addobj('min',c)
mp.addcstr(A,'>=',1)
mp.addctype('B')
spy(A)
%% (Alt 1) Use INTLINPROG
ilp = mp.milp2ilp
x = intlinprog(ilp{:});
nNF = sum(x)
%% (Alt 2) Use Gurobi
clear model params
model = mp.milp2gb;
params.outputflag = 1;
result = gurobi(model,params);
x = result.x;
nNF = sum(x)
%% Plot solution
idx = find(x);
s.Name(idx)
makemap(s.XY)
pplot(s.XY,'r.')
pplot(s.XY(idx,:),'go')
pplot(s.XY(idx,:),s.Name(idx))

%% EXAMPLE 8: Bin Packing Problem
%% Pack 20 objects into min number of bins of capacity 10
m = 20
M = 1:m;
V = 10
rng(123)
v = randi(5,1,m)
mp = Milp('Bin Packing')
mp.addobj('min',ones(1,m),zeros(m))
for i = M
   mp.addcstr({V,{i}},'>=',{v,{i,':'}})   % V*yi >= sum_j(vj*xij)
end
for j = M
   mp.addcstr(0,{':',j},'=',1)            % sum_i(xij) = 1
end
mp.addctype('B','B')
%% Use INTLINPROG to solve
ilp = mp.milp2ilp
x = intlinprog(ilp{:});
x = mp.namesolution(x);
B = arrayfun(@(i) find(x.arg2(i,:)),find(x.arg1),'UniformOutput',false);
B{:}
