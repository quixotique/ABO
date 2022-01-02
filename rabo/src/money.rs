use rusty_money::iso;

pub use rusty_money::MoneyError;

pub type Currency = rusty_money::iso::Currency;
pub type Money = rusty_money::Money<'static, Currency>;

pub const DEFAULT_CURRENCY: &Currency = iso::AUD;
