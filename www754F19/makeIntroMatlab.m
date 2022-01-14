%% Introduction to Matlab

%% Array Manipulation
%%
2 + 3
%%
x = 2 + 3
%%
x + 1
%%
x = x + 1
%%
% x += 1
%%
x = x +  1
%%
x = [1 2 3]
%%
x = [
1
2
3]
%%
x = [1 2 3]'
%%
x = [1; 2; 3]
%%
x
%%
x(2) = 5
%%
a = 1:5
%%
a = 1:.5:5
%%
a = 1:1:5
%%
a = 1:2:15
%%
a = ones(1,5)
%%
a = zeros(1,5)
%%
A = zeros(2,3)
%%
A(1,2) = 3
%%
a = ones(1,5)*5
%%
a = ones(1,5) + 3
%%
a = rand(1,5)
%%
rng(2017)
a = rand(1,5)
%%
a = rand(1,5)
%%
rng(2017)
a = rand(1,5)
%%
a = rand(1,5)
%%
rng(2027)
a = rand(1,5)
%%
a = randi(10)
%%
a = randi(10)
%%
a = randi(100)
%%
a = randi(100)
%%
a = randi(100)
%%
randperm(5)
%%
randperm(5)
%%
a = randi(100,2,3)

%% Multiplication and Addition
%% 
A = [1 2 3; 4 5 6]
%%
A = [1 2 3; 4 5 6];
b = [2 4 6]'
c = [3 5];
%% 2x3 + 1x1 => 2x3 (compatible sizes)
A + 2
%% 2x3 * 1x1 => 2x3 (compatible sizes)
A * 2
%% 1x3 * 3x1 => 1x1 (matrix multiplication)
b' * b
%% 3x1 * 1x3 => 3x3 (matrix multiplication)
b * b'
%% 2x3 * 3x1 => 2x1 (matrix multiplication)
A * b
%% 2x3 * 1x2 => Error 
A * c
%% 1x2 * 2x3 => 1x3 (matrix multiplication)
c * A
%% 3x2 * 2x1 => 3x1 (matrix multiplication)
A' * c'
%% 2x3 .* 3x1 => Error
A .* b
%% 2x3 .* 1x3 => 2x3 (compatible sizes)
A .* b'
%% 2x3 .* 1x2 => Error
A .* c
%% 2x3 .* 2x1 => 2x3 (compatible sizes)
A .* c'
%% Alternate (old way): 2x1 * 1x3 => 2x3 (matrix multiplication) 
c' * ones(1,3)
A .* (c'*ones(1,3))
%% 3x1 .* 1x2 => 3x2 (compatible sizes)
b .* c
%%
clc
clear all

%% Example: Minimum-Distance Location
%%
P = [1 1; 7 1; 4 5];
x = [2 3];
%% 
x - P
%%
(x - P)^2
%%
(x - P).^2
%%
sum((x - P).^2)
%%
sum((x - P).^2, 1)
%%
sum((x - P).^2, 2)
%%
sqrt(sum((x - P).^2, 2))
%%
d = sqrt(sum((x - P).^2, 2))
%%
fh = @(x) sqrt(sum((x - P).^2, 2))
%%
fh(x)
%%
fh(2*x)
%%
fh([0 0])
%%
fh([4 3])
%%
fh = @(x) sum(sqrt(sum((x - P).^2, 2)))
%%
fh([4 3])
%%
xopt = fminsearch(fh,[0 0])
%%
fh(xopt)
%%
xopt = fminsearch(fh,[100 100])
%%
fh([0 0])
%%
fh([0 0]')
%%
fh = @(x) sum(sqrt(sum((x(:)' - P).^2, 2)))
%%
fh([0 0]')
%%
mysumdist(x,P)
%%
mysumdist(x,2*P)
%%
mysumdist([0 0],P)
%%
mysumdist([0 0]',P)

%%
help mysumdist
%%
help sum
%%
doc sum
