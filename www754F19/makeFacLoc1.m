% Facility Location 1: Single-Facility Location

%% 2-D Euclidean Distance
%% Data
P = [1 1; 7 1; 4 5]   % Location of each EF
%% Create Euclidean-distance function handle
d2h = @(x,P) sqrt(sum((x - P).^2, 2))
%% Minisum Distance Location
TDh = @(x) sum(d2h(x,P))        % TD function handle
x0 = mean(P,1);                 % Use mean EF as intial location
x = fminsearch(TDh,x0)          % x* = argmin_x(TD)
TD = TDh(x)                     % TD* = TD(x*)
[x,TD] = fminsearch(TDh,x0)     % Alternate: TD as second output
%% Plot EFs
plot(P(:,1),P(:,2),'ks'),shg
hold on
axis equal
%% Plot NF
plot(x(1),x(2),'b*'),shg
hold off
%% Fermat Problem: Check if all angles 120 degrees
ang = 180*atan2(P(:,2) - x(2), P(:,1) - x(1))/pi  % Angles CC from east
diff(ang)  % All angles 120 degrees

%% 2-D Minisum Weighted-Distance Location
P = [1 1; 7 1; 4 5];
w = [5 3 4]          % Monetary weight for each EF
w.*d2h(x,P)          % Must force w to be column vector using w(:)
TCh = @(x) sum(w(:).*d2h(x,P))
[x,TC] = fminsearch(TCh,x0)
w(3) = sum(w) + 1    % Majority Theorem (add 1 so > W/2)
TCh = @(x) sum(w(:).*d2h(x,P))   % Need to re-define TC since w changed
[x,TC] = fminsearch(TCh,x0)

%% Example: 1-D Location with Procurement and Distribution Costs
%% First, determine monetary weights
% Outbound
fout = [10 20 30];      % ton/yr
rout = 1.00;            % $/ton-mi
wout = fout * rout      % $/mi-yr
% Inbound
BOM = [2 0.5];          % Bill-of-material ratio
fin = BOM * sum(fout)   % ton/yr
rin = 0.33;             % $/ton-mi
win = fin .* rin        % $/mi-yr
w = [win wout]          % $/mi-yr
%% Next, determine location
P = [50 270 150 190 420]';
d2h = @(x,P) sqrt(sum((x - P).^2, 2));  % mi
TCh = @(x) sum(w(:).*d2h(x,P));         % $/yr
x = fminsearch(TCh,mean(P,1))
%% Weight gaining or weight losing
[sum(fin) sum(fout)]    % Physical weight (ton/yr)
[sum(win) sum(wout)]    % Monetary weight ($/mi-yr)  

%% 2-D Minimax
P = [1 1; 7 1; 4 5];
d2h = @(x,P) sqrt(sum((x - P).^2, 2));
TCh = @(x) max(d2h(x,P))
[x,TC] = fminsearch(TCh,mean(P,1))
d = d2h(x,P)

%% 2-D Maximin
%% Unbounded solution
TCh = @(x) -min(d2h(x,P))           % Minus sign to convert min to max
[x,TC] = fminsearch(TCh,mean(P,1))
[x,TC] = fminsearch(TCh,[0 0])
%% Plot surface
[X,Y] = meshgrid(-4:.2:12,-4:.2:10);
Z = zeros(size(X));
for i = 1:size(X,1)
    for j = 1:size(X,2)
        Z(i,j) = TCh([X(i,j) Y(i,j)]);
    end
end
figure
surfc(X,Y,Z),shg,hold on
%% Feasible Region
R = [min(P,[],1)-1; max(P,[],1)+1]
isinR = @(x) x(1)>=R(1,1)&&x(1)<=R(2,1)&&x(2)>=R(1,2)&&x(2)<=R(2,2)
isinR([1 1])
isinR([10 10])
type iff
iff(isinR([1 1]),'yes','no')
iff(isinR([10 10]),'yes','no')
%% Bounded Maximin
TCh = @(x) iff(isinR(x),-min(d2h(x,P)),Inf)
TCh([1 1])
TCh([2 2])
TCh([-4 -4])
x0 = mean(P,1), [x,TC] = fminsearch(TCh,x0)
x0 = [0 0], [x,TC] = fminsearch(TCh,x0)
x0 = P(1,:), [x,TC] = fminsearch(TCh,x0)
x0 = P(2,:), [x,TC] = fminsearch(TCh,x0)
x0 = P(3,:), [x,TC] = fminsearch(TCh,x0)
%% Random starting point
% set seed
rng(1234)
%% run
x0 = R(1,:) + diff(R).*rand(1,size(R,2))
[x,TC] = fminsearch(TCh,x0)



