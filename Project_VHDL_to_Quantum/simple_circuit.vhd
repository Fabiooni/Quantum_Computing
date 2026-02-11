-- simple_circuit.vhd
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity BlackBox is
    Port ( A : in  STD_LOGIC;
           B : in  STD_LOGIC;
           C : in  STD_LOGIC;
           Y : out STD_LOGIC);
end BlackBox;

architecture Behavioral of BlackBox is
begin
    -- Logica: Y è 1 solo se (A e B) sono 1 OPPURE (C è 0) ... esempio a caso
    -- In sintassi Python/Tweedledum per l'oracolo: (A & B) ^ C (per esempio)
    
    -- Esempio VHDL supportato dal nostro parser minimale:
    Y <= (A and B) and (not C);
    
end Behavioral;
